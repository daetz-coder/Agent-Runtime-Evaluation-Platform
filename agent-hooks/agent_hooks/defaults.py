"""默认空操作实现 — 独立运行时使用，零开销。"""

from __future__ import annotations

from typing import Any


class NoOpHooks:
    """所有钩子方法为空操作。"""

    async def on_session_start(
        self, goal: str, session_id: str, context: dict[str, Any]
    ) -> None:
        pass

    async def on_llm_call(
        self,
        model: str,
        messages: list[dict],
        response: str,
        usage: dict[str, int] | None = None,
    ) -> None:
        pass

    async def on_tool_call(
        self,
        tool_name: str,
        args: dict[str, Any],
        result: Any = None,
        duration_ms: float | None = None,
    ) -> None:
        pass

    async def on_retrieval(
        self,
        query: str,
        results: list[dict[str, Any]],
        duration_ms: float | None = None,
    ) -> None:
        pass

    async def on_key_facts(
        self,
        facts: list[str],
        scope: str = "session",
    ) -> None:
        pass

    async def on_response(self, session_id: str, response: str) -> None:
        pass

    async def on_error(self, session_id: str, error: Exception) -> None:
        pass

    async def on_session_end(self, session_id: str) -> None:
        pass
