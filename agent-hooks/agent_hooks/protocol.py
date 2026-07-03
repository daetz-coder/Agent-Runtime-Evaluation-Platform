"""Agent 生命周期钩子协议定义。

提供两层接口：
- 通用层（trace/step）：任何 Agent 都能用，格式自定义
- 结构化层（retrieval/tool_call/llm_call 等）：可选，提供更精确的评估数据

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

    # ── 通用层：任何 Agent 都能用 ─────────────────────────

    async def on_trace(
        self,
        action: str,
        input: dict[str, Any] | None = None,
        output: dict[str, Any] | None = None,
        duration_ms: float | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        """通用追踪记录。action 自定义（如 "search", "generate", "validate"）。"""
        ...

    async def on_step(
        self,
        name: str,
        detail: str = "",
        status: str = "ok",
    ) -> None:
        """步骤记录。最简单的接口，一句话描述 Agent 做了什么。"""
        ...

    # ── 会话生命周期 ─────────────────────────────────────

    async def on_session_start(
        self, goal: str, session_id: str, context: dict[str, Any]
    ) -> None: ...

    async def on_session_end(self, session_id: str) -> None: ...

    # ── 结构化层：可选，提供更精确的评估数据 ─────────────

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
