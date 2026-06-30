"""
轻量级轨迹收集器 — 零外部依赖，仅使用标准库 + httpx。

特性：
- 线程安全（threading.Lock）
- 批量上传 + 失败回退缓冲 + 指数退避重试
- 离线模式：不配置 EVAL_API_BASE_URL 时纯内存缓冲
- 支持全部 14 种轨迹动作类型
- 错误日志（不静默吞异常）
- 单例模式 + reset()/close() 生命周期管理
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
    val = os.environ.get(key, "").lower()
    if val in ("1", "true", "yes", "on"):
        return True
    if val in ("0", "false", "no", "off"):
        return False
    return default


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, ""))
    except (ValueError, TypeError):
        return default


def _env_str(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


# ── ActionType 常量 ──


class ActionType:
    PLAN = "plan"
    PLAN_UPDATE = "plan_update"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    MEMORY_WRITE = "memory_write"
    MEMORY_READ = "memory_read"
    STATE_CHANGE = "state_change"
    THINK = "think"
    REPLAN = "replan"
    FAILURE = "failure"
    NODE_EXECUTE = "node_execute"
    TOOL_DECISION = "tool_decision"
    RETRIEVAL = "retrieval"
    EVIDENCE = "evidence"

    ALL_TYPES = {
        PLAN,
        PLAN_UPDATE,
        TOOL_CALL,
        TOOL_RESULT,
        MEMORY_WRITE,
        MEMORY_READ,
        STATE_CHANGE,
        THINK,
        REPLAN,
        FAILURE,
        NODE_EXECUTE,
        TOOL_DECISION,
        RETRIEVAL,
        EVIDENCE,
    }


def _short(value: Any, limit: int = 4000) -> Any:
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
    if value is None:
        return None
    if isinstance(value, str):
        return _short(value, limit)
    return _short(json.dumps(value, ensure_ascii=False, default=str), limit)


class _BoundedSet:
    """有上限的去重集合，超出时淘汰最早的键。"""

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
    """Per-request collector state (isolated via ContextVar)."""

    task_id: Optional[str] = None
    remote_task_created: bool = False
    step_counter: int = 0
    steps: List[Dict[str, Any]] = field(default_factory=list)
    seen_events: _BoundedSet = field(default_factory=lambda: _BoundedSet(max_size=5000))
    eval_triggered: bool = False
    goal_context: Optional[Dict[str, Any]] = None


_collector_session: ContextVar[Optional[_CollectorSession]] = ContextVar("_collector_session", default=None)


class TrajectoryCollector:
    """线程安全轨迹收集器。

    单例 HTTP 客户端 + ContextVar 会话隔离，避免并发 Wiki 对话互相覆盖 task_id。
    支持 reset() 重置状态和 close() 释放资源。
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
            self._inprocess = _env_bool("EVAL_INPROCESS", True)

            import httpx

        self._client: Optional[httpx.Client] = None

    def _session(self) -> _CollectorSession:
        session = _collector_session.get()
        if session is None:
            session = _CollectorSession()
            _collector_session.set(session)
        return session

    def _new_session(self) -> _CollectorSession:
        session = _CollectorSession()
        _collector_session.set(session)
        return session

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def task_id(self) -> Optional[str]:
        return self._session().task_id

    def use_inprocess(self) -> bool:
        """Use direct DB writes instead of HTTP when embedded in the same platform."""
        if not self._inprocess or not self._enabled:
            return False
        base = self._api_base.rstrip("/")
        return base in (
            "http://127.0.0.1:8000",
            "http://localhost:8000",
        ) or base.startswith("http://127.0.0.1:") or base.startswith("http://localhost:")

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
        """Async start — uses in-process DB when embedded (no HTTP loopback)."""
        if not self.use_inprocess():
            import asyncio
            return await asyncio.to_thread(self.start, goal, context)

        session = self._new_session()
        session.task_id = str(uuid.uuid4())
        session.remote_task_created = False
        session.eval_triggered = False

        if not self._enabled:
            return session.task_id

        from app.collectors.inprocess_transport import create_task_record

        session.task_id = await create_task_record(session.task_id, goal, context)
        session.remote_task_created = True
        session.goal_context = context

        self.record(
            ActionType.PLAN,
            {"goal": goal, "context": _short(context or {})},
        )
        return session.task_id

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
        """Async finish — in-process DB flush avoids HTTP self-deadlock."""
        session = self._session()
        if not session.task_id:
            return None
        self.record(ActionType.THINK, {"thought": "Run finished"})

        if self.use_inprocess() and session.remote_task_created:
            from app.collectors.inprocess_transport import persist_collector_session

            with self._buffer_lock:
                steps_to_send = list(session.steps)
                session.steps = []

            await persist_collector_session(
                session.task_id,
                steps_to_send,
                auto_run=auto_run and not session.eval_triggered,
                context=session.goal_context,
            )
            if auto_run:
                session.eval_triggered = True
            return session.task_id

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

            if len(session.steps) >= self._batch_size and not self.use_inprocess():
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
        if self.use_inprocess():
            return
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
    return TrajectoryCollector()


def reset_collector() -> None:
    """Reset collector state and destroy singleton (for tests)."""
    _collector_session.set(_CollectorSession())
    TrajectoryCollector._reset_singleton()
