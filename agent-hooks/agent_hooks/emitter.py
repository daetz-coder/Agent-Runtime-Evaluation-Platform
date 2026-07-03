"""全局 Emitter — 注册 hooks 实现 + 触发事件 + 异常隔离。

Agent 项目通过 emit 实例调用事件，评估平台通过 register() 注入实现。
"""

from __future__ import annotations

import logging
from typing import Any

from agent_hooks.defaults import NoOpHooks
from agent_hooks.protocol import AgentHooks

logger = logging.getLogger("agent_hooks")


class Emitter:
    """事件发射器。

    内部持有 hooks 实例（默认 NoOpHooks），emit_* 方法调用对应 hooks 方法。
    所有调用都有 try/except 保护，hooks 出错不影响 agent 主流程。
    """

    def __init__(self) -> None:
        self._hooks: AgentHooks = NoOpHooks()

    def register(self, hooks: AgentHooks) -> None:
        """注册外部 hooks 实现（评估平台在启动时调用）。"""
        self._hooks = hooks
        logger.info("Agent hooks registered: %s", type(hooks).__name__)

    @property
    def hooks(self) -> AgentHooks:
        return self._hooks

    async def session_start(
        self, goal: str, session_id: str, context: dict[str, Any] | None = None
    ) -> None:
        try:
            await self._hooks.on_session_start(goal, session_id, context or {})
        except Exception as e:
            logger.debug("Hook on_session_start error: %s", e)

    async def llm_call(
        self,
        model: str,
        messages: list[dict],
        response: str,
        usage: dict[str, int] | None = None,
    ) -> None:
        try:
            await self._hooks.on_llm_call(model, messages, response, usage)
        except Exception as e:
            logger.debug("Hook on_llm_call error: %s", e)

    async def tool_call(
        self,
        tool_name: str,
        args: dict[str, Any],
        result: Any = None,
        duration_ms: float | None = None,
    ) -> None:
        try:
            await self._hooks.on_tool_call(tool_name, args, result, duration_ms)
        except Exception as e:
            logger.debug("Hook on_tool_call error: %s", e)

    async def retrieval(
        self,
        query: str,
        results: list[dict[str, Any]],
        duration_ms: float | None = None,
    ) -> None:
        try:
            await self._hooks.on_retrieval(query, results, duration_ms)
        except Exception as e:
            logger.debug("Hook on_retrieval error: %s", e)

    async def key_facts(
        self,
        facts: list[str],
        scope: str = "session",
    ) -> None:
        try:
            await self._hooks.on_key_facts(facts, scope)
        except Exception as e:
            logger.debug("Hook on_key_facts error: %s", e)

    async def response(self, session_id: str, response: str) -> None:
        try:
            await self._hooks.on_response(session_id, response)
        except Exception as e:
            logger.debug("Hook on_response error: %s", e)

    async def error(self, session_id: str, error: Exception) -> None:
        try:
            await self._hooks.on_error(session_id, error)
        except Exception as e:
            logger.debug("Hook on_error error: %s", e)

    async def session_end(self, session_id: str) -> None:
        try:
            await self._hooks.on_session_end(session_id)
        except Exception as e:
            logger.debug("Hook on_session_end error: %s", e)
