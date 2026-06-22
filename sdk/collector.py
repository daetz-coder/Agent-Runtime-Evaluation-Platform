"""
轻量级轨迹收集器 — 零外部依赖，仅使用标准库 + httpx。

特性：
- 线程安全（threading.Lock）
- 批量上传 + 失败回退缓冲
- 离线模式：不配置 EVAL_API_BASE_URL 时纯内存缓冲
- 支持全部 14 种轨迹动作类型
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


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


class TrajectoryCollector:
    """线程安全轨迹收集器。

    单例模式，通过 get_collector() 获取。
    """

    _instance: Optional["TrajectoryCollector"] = None
    _instance_lock = threading.Lock()

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
        self._initialized = True

        self._task_id: Optional[str] = None
        self._remote_task_created = False
        self._step_counter = 0
        self._steps: List[Dict[str, Any]] = []
        self._buffer_lock = threading.Lock()
        self._flush_lock = threading.Lock()
        self._seen_events: set = set()

        self._enabled = _env_bool("EVAL_ENABLED", True)
        self._api_base = _env_str("EVAL_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
        self._batch_size = _env_int("EVAL_BATCH_SIZE", 10)

        import httpx
        self._client: Optional[httpx.Client] = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def task_id(self) -> Optional[str]:
        return self._task_id

    # ── 任务生命周期 ──

    def start(self, goal: str, context: Optional[Dict[str, Any]] = None) -> str:
        self._task_id = str(uuid.uuid4())
        self._remote_task_created = False
        self._step_counter = 0
        self._steps = []
        self._seen_events = set()

        if not self._enabled:
            return self._task_id

        try:
            r = self._http().post(
                f"{self._api_base}/api/v1/tasks/",
                json={"goal": goal, "context": _short(context or {})},
                timeout=10.0,
            )
            r.raise_for_status()
            self._task_id = r.json()["id"]
            self._remote_task_created = True
        except Exception:
            pass

        self.record(
            ActionType.PLAN,
            {"goal": goal, "context": _short(context or {})},
        )
        return self._task_id

    def finish(self, *, auto_run: bool = False) -> Optional[str]:
        if not self._task_id:
            return None
        self.record(ActionType.THINK, {"thought": "Run finished"})
        self._flush(block=True)

        if auto_run and self._remote_task_created:
            try:
                r = self._http().post(
                    f"{self._api_base}/api/v1/evaluations/",
                    json={"task_id": self._task_id},
                    timeout=10.0,
                )
                r.raise_for_status()
            except Exception:
                pass
        return self._task_id

    # ── 核心记录方法 ──

    def record(
        self,
        action_type: str,
        action_detail: Dict[str, Any],
        observation: Any = None,
        *,
        dedupe_key: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        if not self._task_id or not self._enabled:
            return None
        if dedupe_key:
            key = f"{action_type}:{dedupe_key}"
            if key in self._seen_events:
                return None
            self._seen_events.add(key)

        with self._buffer_lock:
            self._step_counter += 1
            step = {
                "step_number": self._step_counter,
                "action_type": action_type,
                "action_detail": _short(action_detail),
                "observation": _observation_text(observation, 4000),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self._steps.append(step)

            if len(self._steps) >= self._batch_size:
                t = threading.Thread(target=self._flush, daemon=True)
                t.start()

            return step

    # ── 便捷记录方法 ──

    def record_node_execute(self, node_name: str, input_data: Any = None, output_data: Any = None) -> None:
        self.record(ActionType.NODE_EXECUTE, {
            "node_name": node_name,
            "input": _short(input_data),
            "output": _short(output_data),
        })

    def record_tool_call(self, tool_name: str, tool_input: Any = None, tool_output: Any = None, duration_ms: Optional[float] = None) -> None:
        self.record(ActionType.TOOL_CALL, {
            "tool_name": tool_name,
            "input": _short(tool_input),
            "duration_ms": duration_ms,
        }, observation=tool_output)

    def record_tool_result(self, tool_name: str, tool_output: Any = None, duration_ms: Optional[float] = None, success: bool = True, error_type: Optional[str] = None) -> None:
        self.record(ActionType.TOOL_RESULT, {
            "tool_name": tool_name,
            "success": success,
            "error_type": error_type,
            "duration_ms": duration_ms,
        }, observation=tool_output)

    def record_think(self, thought: str) -> None:
        self.record(ActionType.THINK, {"thought": thought})

    def record_llm_call(self, model: str, messages: Any = None, response: Any = None, duration_ms: Optional[float] = None) -> None:
        self.record(ActionType.TOOL_DECISION, {
            "model": model,
            "messages": _short(messages, 1000),
            "response": _short(response, 1000),
            "duration_ms": duration_ms,
        })

    def record_state_change(self, state_before: Dict[str, Any], state_after: Dict[str, Any], trigger: str = "", node_name: str = "") -> None:
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
                            k for k in set(list(old_val.keys()) + list(new_val.keys()))
                            if old_val.get(k) != new_val.get(k)
                        ][:10],
                    }
                else:
                    diff[key] = {
                        "old": str(old_val)[:100] if old_val is not None else "None",
                        "new": str(new_val)[:100] if new_val is not None else "None",
                    }
        self.record(ActionType.STATE_CHANGE, {
            "node_name": node_name,
            "trigger": trigger,
            "diff": diff,
        })

    def record_failure(self, error_type: str, error_message: str, context: str = "", recoverable: bool = True, node_name: str = "", stack_trace: Optional[str] = None) -> None:
        self.record(ActionType.FAILURE, {
            "error_type": error_type,
            "error_message": error_message[:2000],
            "context": context,
            "recoverable": recoverable,
            "node_name": node_name,
            "stack_trace": (stack_trace or "")[:1000],
        })

    def record_plan_update(self, milestone_status: Dict[str, str], next_action: str, reason: str = "", remaining_steps: Optional[List[str]] = None) -> None:
        self.record(ActionType.PLAN_UPDATE, {
            "milestone_status": milestone_status,
            "next_action": next_action,
            "reason": reason,
            "remaining_steps": remaining_steps or [],
        })

    def record_memory_write(self, key: str, value: Any, source: str = "", memory_type: str = "fact") -> None:
        self.record(ActionType.MEMORY_WRITE, {
            "key": key,
            "value": value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)[:2000],
            "source": source,
            "memory_type": memory_type,
        })

    def record_memory_read(self, key: str, value: Any = None, context: str = "", hit: bool = True) -> None:
        self.record(ActionType.MEMORY_READ, {
            "key": key,
            "value": value if isinstance(value, str) else (json.dumps(value, ensure_ascii=False, default=str)[:2000] if value else None),
            "context": context,
            "hit": hit,
        })

    def record_retrieval(self, query: str, retrieved_docs: List[Dict[str, Any]], source: str = "", top_k: int = 3, duration_ms: Optional[float] = None) -> None:
        self.record(ActionType.RETRIEVAL, {
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
        })

    def record_evidence(self, evidence_type: str, sources: Dict[str, Any], final_prompt_messages: Optional[List[Dict[str, str]]] = None, context: str = "") -> None:
        truncated = None
        if final_prompt_messages:
            truncated = [{"role": m.get("role", "unknown"), "content": str(m.get("content", ""))[:1000]} for m in final_prompt_messages]
        self.record(ActionType.EVIDENCE, {
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
        })

    def get_steps(self) -> List[Dict[str, Any]]:
        with self._buffer_lock:
            return list(self._steps)

    # ── 内部方法 ──

    def _flush(self, block: bool = False) -> None:
        if not self._flush_lock.acquire(blocking=block):
            return
        try:
            with self._buffer_lock:
                if not self._steps:
                    return
                steps_to_send = list(self._steps)
                self._steps = []

            if not self._remote_task_created or not self._task_id:
                return

            try:
                r = self._http().post(
                    f"{self._api_base}/api/v1/tasks/{self._task_id}/trajectory",
                    json=steps_to_send,
                    timeout=10.0,
                )
                r.raise_for_status()
            except Exception:
                with self._buffer_lock:
                    self._steps = steps_to_send + self._steps
        finally:
            self._flush_lock.release()

    def _http(self):
        if self._client is None:
            import httpx
            self._client = httpx.Client(timeout=10.0)
        return self._client


# ── 全局单例 ──

def get_collector() -> TrajectoryCollector:
    return TrajectoryCollector()
