"""
sdk.collector — 轻量级轨迹收集器（TrajectoryCollector）

本模块是 SDK 的核心，负责采集 Agent 运行时的每一步操作轨迹，
并通过 HTTP 或进程内直写的方式将数据推送到评估平台。

═══════════════════════════════════════════════════════════════════
架构概览
═══════════════════════════════════════════════════════════════════

    Agent 代码                     评估平台
        │                              ▲
        ▼                              │
  record_*()  ──→  内存缓冲  ──→  批量 flush  ──→  HTTP / DB 直写
        │                              │
        └── 失败时本地重缓冲 ──────────┘

═══════════════════════════════════════════════════════════════════
核心特性
═══════════════════════════════════════════════════════════════════

- **线程安全**：使用 threading.Lock 保护共享缓冲区
- **会话隔离**：通过 ContextVar 实现并发请求间的 task_id 隔离
- **批量上传**：轨迹步骤累积到 EVAL_BATCH_SIZE 后自动 flush
- **失败回退**：flush 失败时步骤回退到本地缓冲，下次 flush 重试
- **指数退避**：HTTP 请求最多重试 3 次（0.5s → 1s → 2s）
- **离线模式**：EVAL_ENABLED=false 时所有操作静默跳过
- **事件去重**：通过 dedupe_key 防止同一事件重复记录
- **单例模式**：全局唯一实例，通过 get_collector() 获取

═══════════════════════════════════════════════════════════════════
环境变量配置
═══════════════════════════════════════════════════════════════════

| 变量                | 默认值                      | 说明                 |
|---------------------|----------------------------|----------------------|
| EVAL_ENABLED        | true                       | 总开关               |
| EVAL_API_BASE_URL   | http://127.0.0.1:8000      | 评估平台地址         |
| EVAL_API_KEY        | ""                         | API 认证密钥         |
| EVAL_BATCH_SIZE     | 10                         | 批量上传阈值         |

═══════════════════════════════════════════════════════════════════
使用示例
═══════════════════════════════════════════════════════════════════

    from sdk.collector import get_collector, ActionType

    collector = get_collector()

    # 1. 开始任务
    task_id = collector.start("实现用户登录功能")

    # 2. 记录轨迹
    collector.record_retrieval("JWT 认证", results, duration_ms=120)
    collector.record_tool_call("sandbox", {"code": "..."}, result)
    collector.record_think("分析测试结果")

    # 3. 结束任务 + 触发评估
    collector.finish(auto_run=True)

"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("sdk.collector")


# ── 配置（纯环境变量，不依赖 pydantic-settings） ──


def _env_bool(key: str, default: bool = True) -> bool:
    """从环境变量读取布尔值。支持 1/true/yes/on 和 0/false/no/off。"""
    val = os.environ.get(key, "").lower()
    if val in ("1", "true", "yes", "on"):
        return True
    if val in ("0", "false", "no", "off"):
        return False
    return default


def _env_int(key: str, default: int) -> int:
    """从环境变量读取整数值，解析失败返回默认值。"""
    try:
        return int(os.environ.get(key, ""))
    except (ValueError, TypeError):
        return default


def _env_str(key: str, default: str = "") -> str:
    """从环境变量读取字符串值。"""
    return os.environ.get(key, default)


# ── ActionType 常量 ──


class ActionType:
    """轨迹记录的动作类型常量。

    定义了 14 种标准化的 Agent 操作类型，覆盖从规划到执行的完整生命周期。
    每种类型对应评估体系中的一个或多个评估维度。

    分类：
        规划类：PLAN, PLAN_UPDATE, REPLAN
        工具类：TOOL_CALL, TOOL_RESULT, TOOL_DECISION
        记忆类：MEMORY_WRITE, MEMORY_READ
        状态类：STATE_CHANGE, NODE_EXECUTE
        思考类：THINK
        检索类：RETRIEVAL, EVIDENCE
        异常类：FAILURE
    """

    # ── 规划输出 ──────────────────────────────────────
    PLAN = "plan"              # 初始规划（milestones / steps）
    PLAN_UPDATE = "plan_update"  # 动态规划更新（milestone 完成、下一步调整）
    REPLAN = "replan"          # 重规划（修改原有计划，ReplanEvaluator 依赖）

    # ── 工具调用 ──────────────────────────────────────
    TOOL_CALL = "tool_call"    # 工具调用（含工具名、输入参数）
    TOOL_RESULT = "tool_result"  # 工具返回（独立记录工具输出、成功/失败）
    TOOL_DECISION = "tool_decision"  # 工具选择决策（LLM 决定调用哪个工具）

    # ── 记忆读写 ──────────────────────────────────────
    MEMORY_WRITE = "memory_write"  # 记忆写入（存入新信息，如 key_facts）
    MEMORY_READ = "memory_read"    # 记忆读取（检索已有信息）

    # ── 状态变化 ──────────────────────────────────────
    STATE_CHANGE = "state_change"  # 状态变化（含 before/after diff）
    NODE_EXECUTE = "node_execute"  # 节点执行（LangGraph 节点输入/输出）

    # ── 思考与推理 ────────────────────────────────────
    THINK = "think"            # 思考过程（推理、分析、LLM 调用记录）

    # ── 异常事件 ──────────────────────────────────────
    FAILURE = "failure"        # 失败/异常事件（含错误类型、堆栈）

    # ── 知识检索与证据构建 ────────────────────────────
    RETRIEVAL = "retrieval"    # 知识库检索（retrieved_docs：检索到的文档列表）
    EVIDENCE = "evidence"      # 证据池构建（最终送给 LLM 的完整证据）

    # 所有合法类型集合（用于校验 action_type 是否合法）
    ALL_TYPES = {
        PLAN, PLAN_UPDATE, TOOL_CALL, TOOL_RESULT,
        MEMORY_WRITE, MEMORY_READ, STATE_CHANGE, THINK,
        REPLAN, FAILURE, NODE_EXECUTE, TOOL_DECISION,
        RETRIEVAL, EVIDENCE,
    }


def _short(value: Any, limit: int = 4000) -> Any:
    """截断过长的值，防止轨迹数据过大。

    递归处理嵌套的 dict/list/str，保证序列化后的单个字段不超过 limit 字符。
    - None/数字/布尔：原样返回
    - 字符串：超过 limit 则截断并加 "…"
    - dict：递归截断每个 value
    - list/tuple：最多保留 50 个元素，递归截断
    - 其他类型：转为字符串后截断
    """
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + "…"
    if isinstance(value, dict):
        return {str(k): _short(v, limit) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_short(v, limit) for v in value[:50]]
    return _short(str(value), limit)


def _observation_text(value: Any, limit: int = 4000) -> Optional[str]:
    """将 observation 值转为可序列化的文本。

    - None → None
    - str → 截断后返回
    - 其他 → JSON 序列化后截断
    """
    if value is None:
        return None
    if isinstance(value, str):
        return _short(value, limit)
    return _short(json.dumps(value, ensure_ascii=False, default=str), limit)


class _BoundedSet:
    """有上限的去重集合（基于 OrderedDict 的 LRU 淘汰）。

    用于事件去重：通过 dedupe_key 参数防止同一事件被重复记录。
    超过 max_size 时自动淘汰最早的键，防止内存泄漏。

    属性:
        _max: 最大容量（默认 5000）
        _od: 底层 OrderedDict，维护插入顺序
    """

    def __init__(self, max_size: int = 5000):
        self._max = max_size
        self._od: OrderedDict[str, None] = OrderedDict()

    def __contains__(self, key: str) -> bool:
        return key in self._od

    def add(self, key: str) -> None:
        if key in self._od:
            self._od.move_to_end(key)
        else:
            if len(self._od) >= self._max:
                self._od.popitem(last=False)
            self._od[key] = None

    def clear(self) -> None:
        self._od.clear()


@dataclass
class _CollectorSession:
    """单次请求的收集器状态（通过 ContextVar 隔离）。

    每个并发请求有独立的 session，避免多个 Wiki 对话互相覆盖 task_id。

    属性:
        task_id: 评估任务 ID（start 时生成）
        remote_task_created: 远程任务是否创建成功
        step_counter: 已记录的步骤数（自动递增）
        steps: 待 flush 的轨迹步骤缓冲区
        seen_events: 已见事件的去重集合（防止重复记录）
        eval_triggered: 评估是否已触发（防止重复触发）
        goal_context: 任务目标的上下文信息
    """

    task_id: Optional[str] = None
    remote_task_created: bool = False
    step_counter: int = 0
    steps: List[Dict[str, Any]] = field(default_factory=list)
    seen_events: _BoundedSet = field(default_factory=lambda: _BoundedSet(max_size=5000))
    eval_triggered: bool = False
    goal_context: Optional[Dict[str, Any]] = None


# ContextVar 实现并发请求间的会话隔离
# 每个 async 任务会自动获得独立的 _CollectorSession 实例
_collector_session: ContextVar[Optional[_CollectorSession]] = ContextVar("_collector_session", default=None)


class TrajectoryCollector:
    """线程安全的 Agent 轨迹收集器（单例模式）。

    ════════════════════════════════════════════════════════════════
    职责
    ════════════════════════════════════════════════════════════════

    1. 创建评估任务（start / start_async）
    2. 记录 Agent 操作轨迹（record / record_*）
    3. 批量上传轨迹数据（_flush / _flush_steps）
    4. 结束任务并触发评估（finish / finish_async）

    ════════════════════════════════════════════════════════════════
    并发模型
    ════════════════════════════════════════════════════════════════

    - 全局单例：通过 get_collector() 获取，所有请求共享同一实例
    - 会话隔离：通过 ContextVar 实现，每个 async 任务有独立的 session
    - 线程安全：buffer_lock 保护 steps 列表，flush_lock 防止并发 flush

    ════════════════════════════════════════════════════════════════
    传输模式
    ════════════════════════════════════════════════════════════════

    统一使用 HTTP 模式：通过 REST API 推送轨迹数据到评估平台。
    异步方法（start_async/finish_async）在线程池中执行 HTTP 请求，不阻塞事件循环。

    """

    _instance: Optional["TrajectoryCollector"] = None
    _instance_lock = threading.Lock()

    # 重试配置
    _MAX_RETRIES = 3
    _RETRY_BASE_DELAY = 0.5  # 秒

    def __new__(cls) -> "TrajectoryCollector":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        # Protect against concurrent __init__ calls (TOCTOU on _initialized).
        with self._instance_lock:
            if self._initialized:
                return
            self._initialized = True

            self._buffer_lock = threading.Lock()
            self._flush_lock = threading.Lock()

            self._enabled = _env_bool("EVAL_ENABLED", True)
            self._api_base = _env_str("EVAL_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
            self._api_key = _env_str("EVAL_API_KEY", "")
            self._batch_size = _env_int("EVAL_BATCH_SIZE", 10)

            import httpx

        self._client: Optional[httpx.Client] = None

    def _session(self) -> _CollectorSession:
        """获取当前请求的 session（不存在则创建）。"""
        session = _collector_session.get()
        if session is None:
            session = _CollectorSession()
            _collector_session.set(session)
        return session

    def _new_session(self) -> _CollectorSession:
        """创建全新的 session（start/start_async 时调用，替换旧 session）。"""
        session = _CollectorSession()
        _collector_session.set(session)
        return session

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def task_id(self) -> Optional[str]:
        return self._session().task_id

    # ── 生命周期管理 ──

    def reset(self) -> None:
        """重置当前上下文中的收集器状态。"""
        with self._buffer_lock:
            _collector_session.set(_CollectorSession())

    def close(self) -> None:
        """关闭 HTTP 客户端，释放资源。"""
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    @classmethod
    def _reset_singleton(cls) -> None:
        """测试用：销毁单例，下次 get_collector() 会重新创建。"""
        with cls._instance_lock:
            if cls._instance is not None:
                cls._instance.close()
            cls._instance = None

    # ── 任务生命周期 ──

    def start(self, goal: str, context: Optional[Dict[str, Any]] = None) -> str:
        """创建评估任务，返回 task_id。"""
        session = self._new_session()
        session.task_id = str(uuid.uuid4())
        session.remote_task_created = False
        session.step_counter = 0
        session.steps = []
        session.seen_events.clear()
        session.eval_triggered = False

        if not self._enabled:
            return session.task_id

        try:
            r = self._http_with_retry(
                "POST",
                f"{self._api_base}/api/v1/tasks/",
                json={"id": session.task_id, "goal": goal, "context": _short(context or {})},
                timeout=30.0,
                idempotent=True,
            )
            if r is not None:
                session.task_id = r.json()["id"]
                session.remote_task_created = True
            else:
                logger.warning(
                    "Failed to create remote task (platform at %s unreachable). "
                    "Trajectory will be buffered locally only.",
                    self._api_base,
                )
        except Exception as exc:
            logger.warning("Task creation failed: %s", exc)

        self.record(
            ActionType.PLAN,
            {"goal": goal, "context": _short(context or {})},
        )
        return session.task_id

    async def start_async(self, goal: str, context: Optional[Dict[str, Any]] = None) -> str:
        """异步创建评估任务（在线程池中执行 HTTP 请求，不阻塞事件循环）。"""
        import asyncio
        return await asyncio.to_thread(self.start, goal, context)

    def finish(self, *, auto_run: bool = False) -> Optional[str]:
        """结束任务，flush 轨迹，可选触发评估。"""
        session = self._session()
        if not session.task_id:
            return None
        self.record(ActionType.THINK, {"thought": "Run finished"})
        self._flush(block=True)

        # Only mark completed if all steps were flushed successfully.
        # After _flush, remaining steps indicate a failed upload.
        with self._buffer_lock:
            flush_succeeded = len(session.steps) == 0

        if session.remote_task_created and flush_succeeded:
            self.update_task(status="completed")
        elif session.remote_task_created and not flush_succeeded:
            logger.warning(
                "Task %s has %d un-flushed steps; marking as 'failed' instead of 'completed'",
                session.task_id,
                len(session.steps),
            )
            self.update_task(status="failed")

        if auto_run and session.remote_task_created and not session.eval_triggered:
            try:
                r = self._http_with_retry(
                    "POST",
                    f"{self._api_base}/api/v1/evaluations/",
                    json={"task_id": session.task_id},
                    timeout=30.0,
                    idempotent=True,
                )
                if r is not None:
                    session.eval_triggered = True
                else:
                    logger.warning("Failed to trigger evaluation for task %s", session.task_id)
            except Exception as exc:
                logger.warning("Evaluation trigger failed: %s", exc)
        return session.task_id

    async def finish_async(self, *, auto_run: bool = False) -> Optional[str]:
        """异步结束任务（在线程池中执行 HTTP 请求，不阻塞事件循环）。"""
        import asyncio
        return await asyncio.to_thread(self.finish, auto_run=auto_run)

    def attach(self, task_id: str) -> None:
        """Bind to an existing remote task without POST /tasks (reuse for confirm/resume)."""
        session = self._session()
        session.task_id = task_id
        session.remote_task_created = True
        session.eval_triggered = False

    def update_task(
        self,
        *,
        goal: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        status: Optional[str] = None,
    ) -> bool:
        """更新已创建的任务（PUT /tasks/{id}）。

        可更新 goal、context、status。返回是否成功。
        """
        session = self._session()
        if not session.task_id or not session.remote_task_created:
            return False

        payload: Dict[str, Any] = {}
        if goal is not None:
            payload["goal"] = goal
        if context is not None:
            payload["context"] = _short(context)
        if status is not None:
            payload["status"] = status

        if not payload:
            return False

        try:
            r = self._http_with_retry(
                "PUT",
                f"{self._api_base}/api/v1/tasks/{session.task_id}",
                json=payload,
            )
            return r is not None
        except Exception as exc:
            logger.warning("Task update failed: %s", exc)
            return False

    # ── 核心记录方法 ──

    def record(
        self,
        action_type: str,
        action_detail: Dict[str, Any],
        observation: Any = None,
        *,
        dedupe_key: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """记录一条轨迹步骤（所有便捷方法的底层实现）。

        流程：
            1. 检查 task_id 和 enabled 状态
            2. dedupe_key 去重（防止同一事件重复记录）
            3. 构建 step dict（含 step_number, action_type, action_detail, observation, timestamp）
            4. 追加到 session.steps 缓冲区
            5. 缓冲区满时自动触发后台 flush

        参数:
            action_type: 动作类型（必须是 ActionType.ALL_TYPES 之一）
            action_detail: 动作详情（会被 _short() 截断到 4000 字符）
            observation: 观察结果（可选，会被序列化为文本）
            dedupe_key: 去重键（可选，格式为 "action_type:dedupe_key"）

        返回:
            构建的 step dict，如果被去重或禁用则返回 None
        """
        session = self._session()
        if not session.task_id or not self._enabled:
            return None
        if dedupe_key:
            key = f"{action_type}:{dedupe_key}"
            if key in session.seen_events:
                return None
            session.seen_events.add(key)

        with self._buffer_lock:
            session.step_counter += 1
            step = {
                "step_number": session.step_counter,
                "action_type": action_type,
                "action_detail": _short(action_detail),
                "observation": _observation_text(observation, 4000),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            session.steps.append(step)

            if len(session.steps) >= self._batch_size:
                steps_snapshot = list(session.steps)
                session.steps = []
                task_id = session.task_id
                remote = session.remote_task_created
                # Capture re-buffer target outside the thread to avoid
                # ContextVar isolation issues (threading.Thread does not
                # inherit parent context on Python < 3.12).
                failed_steps: List[Dict[str, Any]] = []
                threading.Thread(
                    target=self._flush_steps,
                    args=(task_id, remote, steps_snapshot, failed_steps),
                    daemon=True,
                ).start()
                # If the thread already finished (unlikely) and failed,
                # re-buffer now; otherwise the next record() call will
                # pick up failed_steps via _rebuffer_failed_steps().
                if failed_steps:
                    with self._buffer_lock:
                        if session.task_id == task_id:
                            session.steps = failed_steps + session.steps

            return step

    # ── 便捷记录方法（14 种 action type） ──

    def record_node_execute(self, node_name: str, input_data: Any = None, output_data: Any = None) -> None:
        """记录 LangGraph 节点执行。

        参数:
            node_name: 节点名称（如 "search", "respond", "decide"）
            input_data: 节点输入（状态快照）
            output_data: 节点输出（执行结果）
        """
        self.record(
            ActionType.NODE_EXECUTE,
            {
                "node_name": node_name,
                "input": _short(input_data),
                "output": _short(output_data),
            },
        )

    def record_tool_call(
        self, tool_name: str, tool_input: Any = None, tool_output: Any = None, duration_ms: Optional[float] = None
    ) -> None:
        """记录工具调用。

        参数:
            tool_name: 工具名称（如 "sandbox", "search_code"）
            tool_input: 工具输入参数
            tool_output: 工具输出结果（存入 observation）
            duration_ms: 调用耗时（毫秒）
        """
        self.record(
            ActionType.TOOL_CALL,
            {
                "tool_name": tool_name,
                "input": _short(tool_input),
                "duration_ms": duration_ms,
            },
            observation=tool_output,
        )

    def record_tool_result(
        self,
        tool_name: str,
        tool_output: Any = None,
        duration_ms: Optional[float] = None,
        success: bool = True,
        error_type: Optional[str] = None,
    ) -> None:
        """记录工具返回结果（独立于 record_tool_call）。

        参数:
            tool_name: 工具名称
            tool_output: 工具输出
            duration_ms: 调用耗时
            success: 是否成功
            error_type: 错误类型（失败时）
        """
        self.record(
            ActionType.TOOL_RESULT,
            {
                "tool_name": tool_name,
                "success": success,
                "error_type": error_type,
                "duration_ms": duration_ms,
            },
            observation=tool_output,
        )

    def record_think(self, thought: str) -> None:
        """记录思考/推理过程。

        参数:
            thought: 思考内容文本
        """
        self.record(ActionType.THINK, {"thought": thought})

    def record_llm_call(
        self, model: str, messages: Any = None, response: Any = None, duration_ms: Optional[float] = None
    ) -> None:
        """记录 LLM 调用（同时记录为 THINK 以保留 LLM 内容语义）。"""
        self.record(
            ActionType.THINK,
            {
                "thought": f"LLM call to {model}",
                "model": model,
                "messages": _short(messages, 1000),
                "response": _short(response, 1000),
                "duration_ms": duration_ms,
            },
        )

    def record_state_change(
        self, state_before: Dict[str, Any], state_after: Dict[str, Any], trigger: str = "", node_name: str = ""
    ) -> None:
        """记录状态变化（自动计算 before/after diff）。

        对 list 类型只记录长度变化，对 dict 类型记录变更的 key 列表，
        对标量类型记录新旧值（截断到 100 字符）。

        参数:
            state_before: 变化前的状态
            state_after: 变化后的状态
            trigger: 触发变化的原因
            node_name: 关联的节点名称
        """
        diff: Dict[str, Any] = {}
        all_keys = set(list(state_before.keys()) + list(state_after.keys()))
        for key in all_keys:
            old_val = state_before.get(key)
            new_val = state_after.get(key)
            if old_val != new_val:
                if isinstance(old_val, list) and isinstance(new_val, list):
                    diff[key] = {"type": "list", "old_len": len(old_val), "new_len": len(new_val)}
                elif isinstance(old_val, dict) and isinstance(new_val, dict):
                    diff[key] = {
                        "type": "dict",
                        "changed_keys": [
                            k
                            for k in set(list(old_val.keys()) + list(new_val.keys()))
                            if old_val.get(k) != new_val.get(k)
                        ][:10],
                    }
                else:
                    diff[key] = {
                        "old": str(old_val)[:100] if old_val is not None else "None",
                        "new": str(new_val)[:100] if new_val is not None else "None",
                    }
        self.record(
            ActionType.STATE_CHANGE,
            {
                "node_name": node_name,
                "trigger": trigger,
                "diff": diff,
            },
        )

    def record_failure(
        self,
        error_type: str,
        error_message: str,
        context: str = "",
        recoverable: bool = True,
        node_name: str = "",
        stack_trace: Optional[str] = None,
    ) -> None:
        """记录失败/异常事件。

        参数:
            error_type: 错误类型名（如 "ValueError", "TimeoutError"）
            error_message: 错误消息（截断到 2000 字符）
            context: 错误上下文描述
            recoverable: 是否可恢复
            node_name: 关联的节点名称
            stack_trace: 堆栈跟踪（截断到 1000 字符）
        """
        self.record(
            ActionType.FAILURE,
            {
                "error_type": error_type,
                "error_message": error_message[:2000],
                "context": context,
                "recoverable": recoverable,
                "node_name": node_name,
                "stack_trace": (stack_trace or "")[:1000],
            },
        )

    def record_plan_update(
        self,
        milestone_status: Dict[str, str],
        next_action: str,
        reason: str = "",
        remaining_steps: Optional[List[str]] = None,
    ) -> None:
        """记录动态规划更新。

        参数:
            milestone_status: 各里程碑的完成状态
            next_action: 下一步计划
            reason: 更新原因
            remaining_steps: 剩余步骤列表
        """
        self.record(
            ActionType.PLAN_UPDATE,
            {
                "milestone_status": milestone_status,
                "next_action": next_action,
                "reason": reason,
                "remaining_steps": remaining_steps or [],
            },
        )

    def record_replan(self, reason: str, new_plan: str = "", trigger: str = "") -> None:
        """记录重规划事件（ReplanEvaluator 依赖此方法）。"""
        self.record(
            ActionType.REPLAN,
            {
                "reason": reason,
                "new_plan": new_plan,
                "trigger": trigger,
            },
        )

    def record_memory_write(self, key: str, value: Any, source: str = "", memory_type: str = "fact") -> None:
        """记录记忆写入。

        参数:
            key: 记忆键名（如 "key_facts", "user_preference"）
            value: 记忆值（非字符串会 JSON 序列化，截断到 2000 字符）
            source: 数据来源（如 "llm_extraction", "user_input"）
            memory_type: 记忆类型（如 "fact", "preference", "context"）
        """
        self.record(
            ActionType.MEMORY_WRITE,
            {
                "key": key,
                "value": value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)[:2000],
                "source": source,
                "memory_type": memory_type,
            },
        )

    def record_memory_read(self, key: str, value: Any = None, context: str = "", hit: bool = True) -> None:
        """记录记忆读取。

        参数:
            key: 记忆键名
            value: 读取到的值
            context: 读取上下文
            hit: 是否命中（缓存命中/未命中）
        """
        self.record(
            ActionType.MEMORY_READ,
            {
                "key": key,
                "value": value
                if isinstance(value, str)
                else (json.dumps(value, ensure_ascii=False, default=str)[:2000] if value else None),
                "context": context,
                "hit": hit,
            },
        )

    def record_retrieval(
        self,
        query: str,
        retrieved_docs: List[Dict[str, Any]],
        source: str = "",
        top_k: int = 3,
        duration_ms: Optional[float] = None,
    ) -> None:
        """记录知识库检索事件。

        从每个文档中提取 title/path/snippet/score，最多记录 top_k 个文档。

        参数:
            query: 检索查询文本
            retrieved_docs: 检索结果文档列表
            source: 检索来源（如 "hybrid_search", "bm25"）
            top_k: 最多记录的文档数
            duration_ms: 检索耗时
        """
        self.record(
            ActionType.RETRIEVAL,
            {
                "query": query,
                "source": source,
                "top_k": top_k,
                "result_count": len(retrieved_docs),
                "duration_ms": duration_ms,
                "retrieved_docs": [
                    {
                        "title": doc.get("title", ""),
                        "path": doc.get("path", ""),
                        "snippet": doc.get("snippet", "")[:500],
                        "score": doc.get("score"),
                    }
                    for doc in retrieved_docs[:top_k]
                ],
            },
        )

    def record_evidence(
        self,
        evidence_type: str,
        sources: Dict[str, Any],
        final_prompt_messages: Optional[List[Dict[str, str]]] = None,
        context: str = "",
    ) -> None:
        """记录证据池构建（最终送给 LLM 的完整证据）。

        汇总各来源的证据数量（检索文档、工具结果、记忆、对话历史），
        并截断最终 prompt 消息到 1000 字符/条。

        参数:
            evidence_type: 证据类型（如 "rag_context", "tool_results"）
            sources: 证据来源字典（含 retrieved_docs, tool_results, memory_results, chat_history）
            final_prompt_messages: 最终发送给 LLM 的消息列表
            context: 上下文描述
        """
        truncated = None
        if final_prompt_messages:
            truncated = [
                {"role": m.get("role", "unknown"), "content": str(m.get("content", ""))[:1000]}
                for m in final_prompt_messages
            ]
        self.record(
            ActionType.EVIDENCE,
            {
                "evidence_type": evidence_type,
                "context": context,
                "sources": {
                    "retrieved_docs_count": len(sources.get("retrieved_docs") or []),
                    "tool_results_count": len(sources.get("tool_results") or []),
                    "memory_results_count": len(sources.get("memory_results") or []),
                    "chat_history_count": sources.get("chat_history_count", 0),
                },
                "final_prompt_messages": truncated,
                "total_message_count": len(truncated) if truncated else 0,
            },
        )

    def get_steps(self) -> List[Dict[str, Any]]:
        """获取当前 session 的所有已缓冲步骤（线程安全快照）。"""
        with self._buffer_lock:
            return list(self._session().steps)

    # ── 内部方法 ──

    def _http_with_retry(
        self,
        method: str,
        url: str,
        *,
        json: Any = None,
        timeout: float = 10.0,
        idempotent: bool = False,
    ) -> Any:
        """带指数退避重试的 HTTP 请求。失败返回 None。

        配合服务端幂等（client task id / 轨迹 step 去重 / 评估 upsert）安全重试。
        """
        import httpx

        last_exc: Optional[Exception] = None
        for attempt in range(self._MAX_RETRIES):
            try:
                headers = {}
                if self._api_key:
                    headers["Authorization"] = f"Bearer {self._api_key}"
                r = self._http().request(method, url, json=json, timeout=timeout, headers=headers)
                r.raise_for_status()
                return r
            except httpx.TimeoutException as exc:
                last_exc = exc
                logger.debug("HTTP %s %s timeout (attempt %d/%d)", method, url, attempt + 1, self._MAX_RETRIES)
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if idempotent and exc.response.status_code in (200, 201, 409):
                    return exc.response
                logger.debug(
                    "HTTP %s %s returned %d (attempt %d/%d)",
                    method,
                    url,
                    exc.response.status_code,
                    attempt + 1,
                    self._MAX_RETRIES,
                )
            except Exception as exc:
                last_exc = exc
                logger.debug("HTTP %s %s failed: %s (attempt %d/%d)", method, url, exc, attempt + 1, self._MAX_RETRIES)

            if attempt < self._MAX_RETRIES - 1:
                delay = self._RETRY_BASE_DELAY * (2**attempt)
                time.sleep(delay)

        logger.warning("HTTP %s %s failed after %d retries: %s", method, url, self._MAX_RETRIES, last_exc)
        return None

    def _flush_steps(
        self,
        task_id: Optional[str],
        remote_created: bool,
        steps_to_send: List[Dict[str, Any]],
        failed_steps: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Upload trajectory steps (may run in a background thread).

        On failure, steps are appended to *failed_steps* (if provided)
        so the caller can re-buffer them in the correct ContextVar session.
        This avoids the ``threading.Thread`` ContextVar isolation bug where
        a new thread cannot see the parent's session.
        """
        if not steps_to_send or not remote_created or not task_id:
            return

        r = self._http_with_retry(
            "POST",
            f"{self._api_base}/api/v1/tasks/{task_id}/trajectory",
            json=steps_to_send,
            timeout=30.0,
            idempotent=True,
        )
        if r is None:
            logger.warning("Trajectory flush failed, %d steps re-buffered", len(steps_to_send))
            if failed_steps is not None:
                failed_steps.extend(steps_to_send)

    def _flush(self, block: bool = False) -> None:
        """将缓冲区中的步骤上传到评估平台。

        参数:
            block: 是否阻塞等待 flush_lock（True 用于 finish()，False 用于批量 flush）
        """
        if not self._flush_lock.acquire(blocking=block):
            return
        try:
            session = self._session()
            with self._buffer_lock:
                if not session.steps:
                    return
                steps_to_send = list(session.steps)
                session.steps = []
                task_id = session.task_id
                remote = session.remote_task_created

            if not remote or not task_id:
                with self._buffer_lock:
                    session.steps = steps_to_send + session.steps
                return

            failed: List[Dict[str, Any]] = []
            self._flush_steps(task_id, remote, steps_to_send, failed_steps=failed)
            if failed:
                with self._buffer_lock:
                    session.steps = failed + session.steps
        finally:
            self._flush_lock.release()

    def _http(self):
        if self._client is None:
            with self._instance_lock:
                if self._client is None:
                    import httpx

                    self._client = httpx.Client(timeout=10.0)
        return self._client


# ── 全局单例 ──


def get_collector() -> TrajectoryCollector:
    """获取 TrajectoryCollector 全局单例实例。

    首次调用时创建实例，后续调用返回同一实例。
    线程安全（通过 _instance_lock 保护）。

    返回:
        TrajectoryCollector 单例实例
    """
    return TrajectoryCollector()


def reset_collector() -> None:
    """重置收集器状态并销毁单例（仅用于测试）。

    清除当前 ContextVar session，销毁单例实例，
    下次 get_collector() 会重新创建。
    """
    _collector_session.set(_CollectorSession())
    TrajectoryCollector._reset_singleton()
