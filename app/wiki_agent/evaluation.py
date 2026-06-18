"""Lightweight runtime-evaluation integration for the wiki agent.

This module intentionally stays local to the example app so the example can
report trajectories to the evaluation platform without importing the platform's
own ``app`` package, which would collide with this backend package name.

支持的 action_type：
- plan / plan_update       — 规划输出
- tool_call / tool_result  — 工具调用与返回
- memory_write / memory_read — 记忆读写
- state_change             — 状态变化
- think / replan           — 思考与重规划
- failure                  — 失败/异常
- node_execute             — 节点执行
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
import traceback
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import httpx

from app.wiki_agent.config import settings

# action_type 常量（与 app.models.action_types 保持一致）
_ACTION_PLAN = "plan"
_ACTION_PLAN_UPDATE = "plan_update"
_ACTION_TOOL_CALL = "tool_call"
_ACTION_TOOL_RESULT = "tool_result"
_ACTION_MEMORY_WRITE = "memory_write"
_ACTION_MEMORY_READ = "memory_read"
_ACTION_STATE_CHANGE = "state_change"
_ACTION_THINK = "think"
_ACTION_REPLAN = "replan"
_ACTION_FAILURE = "failure"
_ACTION_NODE_EXECUTE = "node_execute"
_ACTION_RETRIEVAL = "retrieval"
_ACTION_EVIDENCE = "evidence"

logger = logging.getLogger(__name__)


def _short(value: Any, limit: int = 4000) -> Any:
    """Keep payloads useful while avoiding huge database rows."""
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + "...[truncated]"
    if isinstance(value, dict):
        return {str(k): _short(v, limit) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_short(v, limit) for v in value[:50]]
    return _short(str(value), limit)


def _observation_text(value: Any, limit: int = 4000) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return _short(value, limit)
    return _short(json.dumps(value, ensure_ascii=False, default=str), limit)


class EvaluationTrace:
    """Collects one wiki-agent run and reports it to the evaluation platform."""

    def __init__(self) -> None:
        self.task_id: str | None = None
        self.remote_task_created = False
        self._step_counter = 0
        self._steps: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._seen_events: set[str] = set()
        self._client: httpx.AsyncClient | None = None

    @property
    def enabled(self) -> bool:
        return bool(settings.EVAL_ENABLED)

    async def start(self, goal: str, context: dict[str, Any] | None = None) -> str:
        self.task_id = str(uuid.uuid4())
        self.remote_task_created = False
        self._step_counter = 0
        self._steps = []
        self._seen_events = set()

        if not self.enabled:
            return self.task_id

        payload = {
            "goal": goal,
            "context": _short(context or {}),
        }
        try:
            response = await self._http().post("/api/v1/tasks/", json=payload)
            response.raise_for_status()
            data = response.json()
            self.task_id = data["id"]
            self.remote_task_created = True
        except Exception as exc:
            logger.warning("Evaluation task creation failed: %s", exc)

        self.record(
            _ACTION_PLAN,
            {
                "goal": goal,
                "steps": [
                    {"description": "Search the wiki knowledge base"},
                    {"description": "Generate a grounded answer"},
                    {"description": "Decide whether knowledge should be updated"},
                    {"description": "Wait for human confirmation before CRUD changes"},
                ],
                "context": _short(context or {}),
            },
        )
        return self.task_id

    def record(
        self,
        action_type: str,
        action_detail: dict[str, Any],
        observation: Any | None = None,
        *,
        dedupe_key: str | None = None,
    ) -> dict[str, Any] | None:
        if not self.task_id or not self.enabled:
            return None
        if dedupe_key:
            key = f"{action_type}:{dedupe_key}"
            if key in self._seen_events:
                return None
            self._seen_events.add(key)

        with self._lock:
            self._step_counter += 1
            step = {
                "step_number": self._step_counter,
                "action_type": action_type,
                "action_detail": _short(action_detail),
                "observation": _observation_text(observation, 4000),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self._steps.append(step)
            return step

    def record_tool_call(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        tool_output: Any = None,
        *,
        duration_ms: float | None = None,
        call_id: str | None = None,
    ) -> None:
        detail = {
            "tool_name": tool_name,
            "input": tool_input,
            "duration_ms": duration_ms,
        }
        self.record(
            _ACTION_TOOL_CALL,
            detail,
            observation=tool_output,
            dedupe_key=call_id or f"{tool_name}:{tool_input}",
        )

    def record_tool_result(
        self,
        tool_name: str,
        tool_output: Any,
        *,
        duration_ms: float | None = None,
        success: bool = True,
        error_type: str | None = None,
        call_id: str | None = None,
    ) -> None:
        """独立记录工具返回结果。"""
        self.record(
            _ACTION_TOOL_RESULT,
            {
                "tool_name": tool_name,
                "success": success,
                "error_type": error_type,
                "duration_ms": duration_ms,
            },
            observation=tool_output,
            dedupe_key=call_id or f"result:{tool_name}",
        )

    # ── Planner 输出 ──────────────────────────────────────────

    def record_plan_update(
        self,
        milestone_status: dict[str, str],
        next_action: str,
        reason: str = "",
        remaining_steps: list[str] | None = None,
    ) -> None:
        """记录动态规划更新（milestone 完成、下一步调整）。"""
        self.record(
            _ACTION_PLAN_UPDATE,
            {
                "milestone_status": milestone_status,
                "next_action": next_action,
                "reason": reason,
                "remaining_steps": remaining_steps or [],
            },
        )

    # ── 记忆读写 ─────────────────────────────────────────────

    def record_memory_write(
        self,
        key: str,
        value: Any,
        source: str = "",
        memory_type: str = "fact",
    ) -> None:
        """记录记忆写入。"""
        self.record(
            _ACTION_MEMORY_WRITE,
            {
                "key": key,
                "value": value if isinstance(value, str) else json.dumps(
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
    ) -> None:
        """记录记忆读取。"""
        self.record(
            _ACTION_MEMORY_READ,
            {
                "key": key,
                "value": value if isinstance(value, str) else (
                    json.dumps(value, ensure_ascii=False, default=str)[:2000] if value else None
                ),
                "context": context,
                "hit": hit,
            },
        )

    # ── 状态变化 ─────────────────────────────────────────────

    def record_state_change(
        self,
        state_before: dict[str, Any],
        state_after: dict[str, Any],
        trigger: str = "",
        node_name: str = "",
    ) -> None:
        """记录状态变化（含 diff）。"""
        diff: dict[str, Any] = {}
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
                    old_str = str(old_val)[:100] if old_val is not None else "None"
                    new_str = str(new_val)[:100] if new_val is not None else "None"
                    diff[key] = {"old": old_str, "new": new_str}

        self.record(
            _ACTION_STATE_CHANGE,
            {
                "node_name": node_name,
                "trigger": trigger,
                "diff": diff,
                "before_keys": list(state_before.keys()),
                "after_keys": list(state_after.keys()),
            },
        )

    # ── 重规划 ─────────────────────────────────────────────

    def record_replan(
        self,
        reason: str,
        old_plan: list[str] | None = None,
        new_plan: list[str] | None = None,
        trigger_step: int | None = None,
    ) -> None:
        """记录重规划事件。"""
        self.record(
            _ACTION_REPLAN,
            {
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
        stack_trace: str | None = None,
    ) -> None:
        """记录失败/异常事件。"""
        self.record(
            _ACTION_FAILURE,
            {
                "error_type": error_type,
                "error_message": error_message[:2000],
                "context": context,
                "recoverable": recoverable,
                "node_name": node_name,
                "stack_trace": (stack_trace or "")[:1000],
            },
        )

    # ── 知识检索 ─────────────────────────────────────────────

    def record_retrieval(
        self,
        query: str,
        retrieved_docs: list[dict[str, Any]],
        source: str = "",
        top_k: int = 3,
        duration_ms: float | None = None,
    ) -> None:
        """
        记录知识库检索结果（retrieved_docs）。

        Args:
            query: 检索查询
            retrieved_docs: 检索到的文档列表，每项含 title/path/snippet/score 等
            source: 检索来源（如 "hybrid_search", "vector_db", "keyword_search"）
            top_k: 请求返回的文档数
            duration_ms: 检索耗时
        """
        self.record(
            _ACTION_RETRIEVAL,
            {
                "query": query,
                "source": source,
                "top_k": top_k,
                "result_count": len(retrieved_docs),
                "duration_ms": duration_ms,
                # 完整记录每个文档的内容
                "retrieved_docs": [
                    {
                        "title": doc.get("title", ""),
                        "path": doc.get("path", ""),
                        "snippet": doc.get("snippet", "")[:500],
                        "score": doc.get("score"),
                        "metadata": {k: str(v)[:200] for k, v in (doc.get("metadata") or {}).items()},
                    }
                    for doc in retrieved_docs
                ],
            },
            observation=f"Retrieved {len(retrieved_docs)} docs for query: {query[:200]}",
        )

    # ── 证据池构建 ───────────────────────────────────────────

    def record_evidence(
        self,
        evidence_type: str,
        sources: dict[str, Any],
        final_prompt_messages: list[dict[str, str]] | None = None,
        context: str = "",
    ) -> None:
        """
        记录最终送给 LLM 的证据池（evidence）。

        Args:
            evidence_type: 证据类型（如 "grounded_response", "decision", "planning"）
            sources: 证据来源汇总，如：
                {
                    "retrieved_docs": [...],      # 知识库检索结果
                    "tool_results": [...],         # 工具返回结果
                    "memory_results": [...],       # 内部记忆
                    "chat_history_count": 5,       # 对话历史条数
                }
            final_prompt_messages: 最终发给 LLM 的消息列表（含 system/user/assistant）
            context: 证据用途说明
        """
        # 对 final_prompt_messages 做截断处理
        truncated_messages = None
        if final_prompt_messages:
            truncated_messages = []
            for msg in final_prompt_messages:
                truncated_messages.append({
                    "role": msg.get("role", "unknown"),
                    "content": str(msg.get("content", ""))[:1000],
                })

        self.record(
            _ACTION_EVIDENCE,
            {
                "evidence_type": evidence_type,
                "context": context,
                "sources": {
                    "retrieved_docs_count": len(sources.get("retrieved_docs") or []),
                    "tool_results_count": len(sources.get("tool_results") or []),
                    "memory_results_count": len(sources.get("memory_results") or []),
                    "chat_history_count": sources.get("chat_history_count", 0),
                    # 记录检索文档摘要
                    "retrieved_docs_summary": [
                        {"title": d.get("title", ""), "path": d.get("path", "")}
                        for d in (sources.get("retrieved_docs") or [])[:10]
                    ],
                    # 记录工具结果摘要
                    "tool_results_summary": [
                        {"tool": r.get("tool", ""), "success": r.get("success", True)}
                        for r in (sources.get("tool_results") or [])[:10]
                    ],
                    # 记录记忆结果
                    "memory_results": [
                        {"key": m.get("key", ""), "hit": m.get("hit", True)}
                        for m in (sources.get("memory_results") or [])[:10]
                    ],
                },
                "final_prompt_messages": truncated_messages,
                "total_message_count": len(truncated_messages) if truncated_messages else 0,
            },
        )

    @asynccontextmanager
    async def node(self, name: str, input_data: Any = None) -> AsyncIterator[None]:
        started = time.perf_counter()
        self.record(
            _ACTION_NODE_EXECUTE,
            {"node_name": name, "phase": "start", "input": _short(input_data)},
        )
        try:
            yield
        except Exception as exc:
            # 记录节点执行错误
            self.record(
                _ACTION_NODE_EXECUTE,
                {"node_name": name, "phase": "error", "error_type": type(exc).__name__},
                observation=str(exc),
            )
            # 独立记录 failure 事件
            self.record_failure(
                error_type=type(exc).__name__,
                error_message=str(exc),
                context=f"Node '{name}' execution failed",
                recoverable=True,
                node_name=name,
                stack_trace=traceback.format_exc()[-1000:],
            )
            raise
        else:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            self.record(
                _ACTION_NODE_EXECUTE,
                {
                    "node_name": name,
                    "phase": "end",
                    "duration_ms": duration_ms,
                },
            )
            # 记录状态变化
            if input_data is not None:
                self.record_state_change(
                    state_before={"phase": "start", "node": name},
                    state_after={"phase": "end", "node": name, "duration_ms": duration_ms},
                    trigger=name,
                    node_name=name,
                )

    async def flush(self) -> None:
        if not self.enabled or not self.remote_task_created or not self.task_id:
            return
        with self._lock:
            steps = list(self._steps)
            self._steps = []
        if not steps:
            return
        try:
            response = await self._http().post(f"/api/v1/tasks/{self.task_id}/trajectory", json=steps)
            response.raise_for_status()
        except Exception as exc:
            logger.warning("Evaluation trajectory upload failed: %s", exc)
            with self._lock:
                self._steps = steps + self._steps

    async def finish(self, *, auto_run: bool | None = None) -> str | None:
        if not self.task_id:
            return None
        self.record(_ACTION_THINK, {"thought": "Wiki agent run finished"})
        await self.flush()

        should_run = settings.EVAL_AUTO_RUN if auto_run is None else auto_run
        if should_run and self.remote_task_created:
            try:
                response = await self._http().post("/api/v1/evaluations/", json={"task_id": self.task_id})
                response.raise_for_status()
            except Exception as exc:
                logger.warning("Evaluation auto-run failed: %s", exc)
        return self.task_id

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=settings.EVAL_API_BASE_URL.rstrip("/"),
                timeout=10.0,
            )
        return self._client


async def maybe_flush(trace: EvaluationTrace | None) -> None:
    if trace is not None:
        await trace.flush()


def get_eval_trace(config: Any) -> EvaluationTrace | None:
    configurable = (config or {}).get("configurable") or {}
    return configurable.get("eval_trace")


async def run_with_trace(coro: Any, trace: EvaluationTrace | None) -> Any:
    try:
        return await coro
    finally:
        await maybe_flush(trace)
