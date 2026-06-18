"""
Trajectory Collector - 收集 Agent 执行轨迹

设计原则：
- 线程安全：支持多线程环境
- 低侵入：不修改原有代码
- 异步上报：后台批量发送数据

支持的 action_type（定义在 app.models.action_types）：
- plan / plan_update       — 规划输出
- tool_call / tool_result  — 工具调用与返回
- memory_write / memory_read — 记忆读写
- state_change             — 状态变化
- think / replan           — 思考与重规划
- failure                  — 失败/异常
- node_execute / tool_decision — 节点执行与工具决策
"""

from __future__ import annotations

import json as _json
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings
from app.models.action_types import ActionType

logger = logging.getLogger(__name__)


class TrajectoryCollector:
    """
    轨迹收集器 - 单例模式

    职责：
    - 收集 LLM 调用、工具调用、节点执行等信息
    - 维护 step_number 和时间戳
    - 批量上报到评估平台后端
    """

    _instance: Optional[TrajectoryCollector] = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._task_id: Optional[str] = None
        self._step_counter: int = 0
        self._steps: List[Dict[str, Any]] = []
        self._buffer_lock = threading.Lock()
        self._flush_lock = threading.Lock()

        # HTTP 客户端
        self._http: Optional[httpx.Client] = None

        # 评估平台地址，可通过 EVAL_API_BASE_URL 覆盖
        self._api_base_url = settings.EVAL_API_BASE_URL.rstrip("/")

        self._initialized = True

    @property
    def task_id(self) -> Optional[str]:
        return self._task_id

    @property
    def is_active(self) -> bool:
        return self._task_id is not None

    def start(self, goal: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        开始收集轨迹

        Args:
            goal: Agent 的目标/用户问题
            context: 额外上下文

        Returns:
            task_id: 任务 ID
        """
        if self._task_id:
            self.stop()

        # 创建后端任务
        try:
            http = self._get_http()
            response = http.post("/api/v1/tasks/", json={
                "goal": goal,
                "context": context or {},
            })
            response.raise_for_status()
            task_data = response.json()
            self._task_id = task_data["id"]
        except Exception as e:
            logger.warning(f"Failed to create task: {e}")
            # 使用本地 task_id
            self._task_id = str(uuid.uuid4())

        # 重置状态
        self._step_counter = 0
        self._steps = []

        logger.info(f"Trajectory collection started: {self._task_id}")
        return self._task_id

    def stop(self) -> Optional[str]:
        """
        停止收集，刷新缓冲区

        Returns:
            task_id: 任务 ID
        """
        if not self._task_id:
            return None

        # 刷新剩余数据
        self._flush()

        task_id = self._task_id
        self._task_id = None
        self._step_counter = 0
        self._steps = []

        logger.info(f"Trajectory collection stopped: {task_id}")
        return task_id

    def record(
        self,
        action_type: str,
        action_detail: Dict[str, Any],
        observation: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        记录一个轨迹步骤

        Args:
            action_type: 动作类型 ("llm_call", "tool_call", "node_execute", etc.)
            action_detail: 动作详情
            observation: 观察结果

        Returns:
            步骤信息
        """
        if not self._task_id:
            return {}

        with self._buffer_lock:
            self._step_counter += 1
            step = {
                "step_number": self._step_counter,
                "action_type": action_type,
                "action_detail": action_detail,
                "observation": observation,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self._steps.append(step)

        # 达到批量大小时上报
        if len(self._steps) >= settings.EVAL_BATCH_SIZE:
            self._flush_async()

        return step

    def record_llm_call(
        self,
        model: str,
        messages: List[Dict[str, str]],
        response: str,
        duration_ms: float = 0,
    ):
        """记录 LLM 调用"""
        return self.record(
            action_type="llm_call",
            action_detail={
                "model": model,
                "messages": messages[:10],
                "response": response[:4000],
                "duration_ms": duration_ms,
            },
            observation=response[:4000],
        )

    def record_node_execute(
        self,
        node_name: str,
        input_data: Any = None,
        output_data: Any = None,
    ):
        """记录节点执行"""
        return self.record(
            action_type="node_execute",
            action_detail={
                "node_name": node_name,
                "input": str(input_data)[:2000] if input_data else None,
                "output": str(output_data)[:2000] if output_data else None,
            },
        )

    def record_think(self, thought: str):
        """记录思考过程"""
        return self.record(
            action_type=ActionType.THINK,
            action_detail={"thought": thought},
        )

    # ── Planner 输出 ──────────────────────────────────────────

    def record_plan(
        self,
        steps: List[Dict[str, Any]],
        goal: str = "",
        milestones: Optional[List[str]] = None,
    ):
        """
        记录初始规划

        Args:
            steps: 规划步骤列表，每项含 description
            goal: 目标描述
            milestones: 里程碑列表
        """
        return self.record(
            action_type=ActionType.PLAN,
            action_detail={
                "goal": goal,
                "steps": steps,
                "milestones": milestones or [],
            },
        )

    def record_plan_update(
        self,
        milestone_status: Dict[str, str],
        next_action: str,
        reason: str = "",
        remaining_steps: Optional[List[str]] = None,
    ):
        """
        记录动态规划更新

        Args:
            milestone_status: 里程碑完成状态，如 {"search": "done", "respond": "in_progress"}
            next_action: 下一步行动
            reason: 更新原因
            remaining_steps: 剩余步骤
        """
        return self.record(
            action_type=ActionType.PLAN_UPDATE,
            action_detail={
                "milestone_status": milestone_status,
                "next_action": next_action,
                "reason": reason,
                "remaining_steps": remaining_steps or [],
            },
        )

    # ── 工具调用与返回 ────────────────────────────────────────

    def record_tool_call(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_output: Optional[str] = None,
        duration_ms: float = 0,
    ):
        """记录工具调用（含输入）"""
        return self.record(
            action_type="tool_call",
            action_detail={
                "tool_name": tool_name,
                "input": tool_input,
                "output": tool_output[:4000] if tool_output else None,
                "duration_ms": duration_ms,
            },
            observation=tool_output[:4000] if tool_output else None,
        )

    def record_tool_result(
        self,
        tool_name: str,
        tool_output: Any,
        duration_ms: float = 0,
        success: bool = True,
        error_type: Optional[str] = None,
    ):
        """
        记录工具返回结果（独立于 tool_call）

        Args:
            tool_name: 工具名
            tool_output: 工具输出
            duration_ms: 耗时
            success: 是否成功
            error_type: 失败时的错误类型
        """
        output_text = tool_output if isinstance(tool_output, str) else _json.dumps(
            tool_output, ensure_ascii=False, default=str
        )[:4000]
        return self.record(
            action_type=ActionType.TOOL_RESULT,
            action_detail={
                "tool_name": tool_name,
                "success": success,
                "error_type": error_type,
                "duration_ms": duration_ms,
            },
            observation=output_text[:4000] if output_text else None,
        )

    # ── 记忆读写 ─────────────────────────────────────────────

    def record_memory_write(
        self,
        key: str,
        value: Any,
        source: str = "",
        memory_type: str = "fact",
    ):
        """
        记录记忆写入

        Args:
            key: 记忆键
            value: 记忆值
            source: 来源（如 "user_input", "tool_output", "inference"）
            memory_type: 记忆类型（如 "fact", "preference", "context"）
        """
        return self.record(
            action_type=ActionType.MEMORY_WRITE,
            action_detail={
                "key": key,
                "value": value if isinstance(value, str) else _json.dumps(
                    value, ensure_ascii=False, default=str
                )[:2000],
                "source": source,
                "memory_type": memory_type,
            },
        )

    def record_memory_read(
        self,
        key: str,
        value: Any = None,
        context: str = "",
        hit: bool = True,
    ):
        """
        记录记忆读取

        Args:
            key: 记忆键
            value: 读取到的值（hit=False 时为 None）
            context: 读取上下文
            hit: 是否命中
        """
        return self.record(
            action_type=ActionType.MEMORY_READ,
            action_detail={
                "key": key,
                "value": value if isinstance(value, str) else (
                    _json.dumps(value, ensure_ascii=False, default=str)[:2000] if value else None
                ),
                "context": context,
                "hit": hit,
            },
        )

    # ── 状态变化 ─────────────────────────────────────────────

    def record_state_change(
        self,
        state_before: Dict[str, Any],
        state_after: Dict[str, Any],
        trigger: str = "",
        node_name: str = "",
    ):
        """
        记录状态变化（含 diff）

        Args:
            state_before: 变化前状态快照
            state_after: 变化后状态快照
            trigger: 触发原因（如节点名、工具名）
            node_name: 关联的节点名
        """
        # 计算 diff
        diff = self._compute_state_diff(state_before, state_after)
        return self.record(
            action_type=ActionType.STATE_CHANGE,
            action_detail={
                "node_name": node_name,
                "trigger": trigger,
                "diff": diff,
                "before_keys": list(state_before.keys()) if isinstance(state_before, dict) else [],
                "after_keys": list(state_after.keys()) if isinstance(state_after, dict) else [],
            },
        )

    @staticmethod
    def _compute_state_diff(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
        """比较两个状态快照，返回变化摘要。"""
        diff: Dict[str, Any] = {}
        all_keys = set(list(before.keys()) + list(after.keys()))
        for key in all_keys:
            old_val = before.get(key)
            new_val = after.get(key)
            if old_val != new_val:
                # 对大对象只记录类型和长度变化
                if isinstance(old_val, list) and isinstance(new_val, list):
                    diff[key] = {
                        "type": "list",
                        "old_len": len(old_val),
                        "new_len": len(new_val),
                    }
                elif isinstance(old_val, dict) and isinstance(new_val, dict):
                    diff[key] = {
                        "type": "dict",
                        "changed_keys": [
                            k for k in set(list(old_val.keys()) + list(new_val.keys()))
                            if old_val.get(k) != new_val.get(k)
                        ][:10],
                    }
                else:
                    old_str = str(old_val)[:100] if old_val is not None else "None"
                    new_str = str(new_val)[:100] if new_val is not None else "None"
                    diff[key] = {"old": old_str, "new": new_str}
        return diff

    # ── 重规划 ─────────────────────────────────────────────

    def record_replan(
        self,
        reason: str,
        old_plan: Optional[List[str]] = None,
        new_plan: Optional[List[str]] = None,
        trigger_step: Optional[int] = None,
    ):
        """
        记录重规划事件

        Args:
            reason: 重规划原因
            old_plan: 原计划步骤
            new_plan: 新计划步骤
            trigger_step: 触发重规划的步骤号
        """
        return self.record(
            action_type=ActionType.REPLAN,
            action_detail={
                "reason": reason,
                "old_plan": old_plan or [],
                "new_plan": new_plan or [],
                "trigger_step": trigger_step,
            },
        )

    # ── 失败/异常 ─────────────────────────────────────────

    def record_failure(
        self,
        error_type: str,
        error_message: str,
        context: str = "",
        recoverable: bool = True,
        node_name: str = "",
        stack_trace: Optional[str] = None,
    ):
        """
        记录失败/异常事件

        Args:
            error_type: 错误类型（如 TimeoutError, ToolExecutionError）
            error_message: 错误消息
            context: 错误上下文
            recoverable: 是否可恢复
            node_name: 发生错误的节点
            stack_trace: 堆栈摘要
        """
        return self.record(
            action_type=ActionType.FAILURE,
            action_detail={
                "error_type": error_type,
                "error_message": error_message[:2000],
                "context": context,
                "recoverable": recoverable,
                "node_name": node_name,
                "stack_trace": (stack_trace or "")[:1000],
            },
        )

    def _flush(self):
        """同步刷新缓冲区"""
        if not self._flush_lock.acquire(blocking=False):
            return

        try:
            if not self._steps or not self._task_id:
                return

            with self._buffer_lock:
                steps_to_send = self._steps.copy()
                self._steps = []

            try:
                http = self._get_http()
                response = http.post(
                    f"/api/v1/tasks/{self._task_id}/trajectory",
                    json=steps_to_send,
                )
                response.raise_for_status()
                logger.debug(f"Sent {len(steps_to_send)} steps")
            except Exception as e:
                logger.warning(f"Failed to send trajectory: {e}")
                # 把数据放回缓冲区
                with self._buffer_lock:
                    self._steps = steps_to_send + self._steps
        finally:
            self._flush_lock.release()

    def _flush_async(self):
        """异步刷新（在后台线程中执行）"""
        thread = threading.Thread(target=self._flush, daemon=True)
        thread.start()

    def _get_http(self) -> httpx.Client:
        """获取 HTTP 客户端"""
        if self._http is None:
            self._http = httpx.Client(
                base_url=self._api_base_url,
                timeout=30.0,
            )
        return self._http


def get_collector() -> TrajectoryCollector:
    """获取收集器单例"""
    return TrajectoryCollector()


def reset_collector():
    """重置收集器"""
    collector = get_collector()
    if collector.is_active:
        collector.stop()
