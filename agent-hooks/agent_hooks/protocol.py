"""Agent 生命周期钩子协议定义。

所有方法都有默认空实现（通过 defaults.py），
评估平台只需实现关心的事件即可。
"""

from __future__ import annotations

from typing import Any, Protocol


class AgentHooks(Protocol):
    """Agent 生命周期钩子接口。

    评估平台实现此接口，通过 register() 注入。
    所有方法都是可选的 — 未实现的方法自动降级为空操作。
    """

    async def on_session_start(
        self, goal: str, session_id: str, context: dict[str, Any]
    ) -> None: ...

    async def on_llm_call(
        self,
        model: str,
        messages: list[dict],
        response: str,
        usage: dict[str, int] | None = None,
    ) -> None: ...

    async def on_tool_call(
        self,
        tool_name: str,
        args: dict[str, Any],
        result: Any = None,
        duration_ms: float | None = None,
    ) -> None: ...

    async def on_retrieval(
        self,
        query: str,
        results: list[dict[str, Any]],
        duration_ms: float | None = None,
    ) -> None: ...

    async def on_key_facts(
        self,
        facts: list[str],
        scope: str = "session",
    ) -> None: ...

    async def on_response(
        self, session_id: str, response: str
    ) -> None: ...

    async def on_error(
        self, session_id: str, error: Exception
    ) -> None: ...

    async def on_session_end(self, session_id: str) -> None: ...
