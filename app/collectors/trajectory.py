"""
Trajectory Collector - 收集 Agent 执行轨迹

设计原则：
- 线程安全：支持多线程环境
- 低侵入：不修改原有代码
- 异步上报：后台批量发送数据
"""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings

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

        # HTTP 客户端
        self._http: Optional[httpx.Client] = None

        # 配置
        self._api_base_url = settings.HOST.replace("0.0.0.0", "127.0.0.1")
        if not self._api_base_url.startswith("http"):
            self._api_base_url = f"http://{self._api_base_url}"
        self._api_base_url = f"{self._api_base_url}:{settings.PORT}"

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
        if len(self._steps) >= 10:
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
                "messages": messages[:3],  # 只保留前 3 条
                "response": response[:500],  # 截断
                "duration_ms": duration_ms,
            },
            observation=response[:200],
        )

    def record_tool_call(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_output: Optional[str] = None,
        duration_ms: float = 0,
    ):
        """记录工具调用"""
        return self.record(
            action_type="tool_call",
            action_detail={
                "tool_name": tool_name,
                "input": tool_input,
                "output": tool_output[:500] if tool_output else None,
                "duration_ms": duration_ms,
            },
            observation=tool_output[:200] if tool_output else None,
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
                "input": str(input_data)[:200] if input_data else None,
                "output": str(output_data)[:200] if output_data else None,
            },
        )

    def record_think(self, thought: str):
        """记录思考过程"""
        return self.record(
            action_type="think",
            action_detail={"thought": thought},
        )

    def _flush(self):
        """同步刷新缓冲区"""
        if not self._steps or not self._task_id:
            return

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
