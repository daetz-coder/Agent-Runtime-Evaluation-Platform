"""Lightweight runtime-evaluation integration for the wiki agent.

This module intentionally stays local to the example app so the example can
report trajectories to the evaluation platform without importing the platform's
own ``app`` package, which would collide with this backend package name.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import httpx

from app.config import settings

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
            "plan",
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

    def resume(self, task_id: str) -> None:
        """继续已有的 task（不创建新 task，step_number 从 0 续接）。"""
        self.task_id = task_id
        self.remote_task_created = True  # 假设远端已存在
        self._step_counter = 0
        self._steps = []
        self._seen_events = set()
        self.record(
            "plan_update",
            {
                "reason": "User sent a follow-up message in the same task",
                "next_action": "Continue with follow-up",
            },
        )

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
            "tool_call",
            detail,
            observation=tool_output,
            dedupe_key=call_id or f"{tool_name}:{tool_input}",
        )

    @asynccontextmanager
    async def node(self, name: str, input_data: Any = None) -> AsyncIterator[None]:
        started = time.perf_counter()
        self.record("node_execute", {"node_name": name, "phase": "start", "input": input_data})
        try:
            yield
        except Exception as exc:
            self.record(
                "node_execute",
                {"node_name": name, "phase": "error", "error_type": type(exc).__name__},
                observation=str(exc),
            )
            raise
        else:
            self.record(
                "node_execute",
                {
                    "node_name": name,
                    "phase": "end",
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
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

    async def update_context(self, extra: dict[str, Any]) -> None:
        """Merge *extra* into the remote task's context (PATCH-style)."""
        if not self.enabled or not self.remote_task_created or not self.task_id:
            return
        try:
            response = await self._http().put(
                f"/api/v1/tasks/{self.task_id}",
                json={"context": _short(extra)},
            )
            response.raise_for_status()
        except Exception as exc:
            logger.warning("Evaluation context update failed: %s", exc)

    async def finish(self, *, auto_run: bool | None = None) -> str | None:
        if not self.task_id:
            return None
        self.record("think", {"thought": "Wiki agent run finished"})
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
