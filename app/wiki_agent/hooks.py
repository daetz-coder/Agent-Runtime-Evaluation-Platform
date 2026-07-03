"""wiki-agent 生命周期钩子接口。

默认所有方法为空操作，不影响独立运行。
外部系统（如评估平台）可通过 register_hooks() 注入实现来采集数据。
"""

from __future__ import annotations

import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class WikiAgentHooks(Protocol):
    """钩子接口，外部系统实现此接口来监听 wiki-agent 生命周期事件。"""

    async def on_session_start(self, goal: str, session_id: str, context: dict) -> None: ...
    async def on_retrieval(self, query: str, results: list[dict], duration_ms: float) -> None: ...
    async def on_key_facts(self, facts: list[str]) -> None: ...
    async def on_response(self, session_id: str, response: str) -> None: ...
    async def on_session_end(self, session_id: str) -> None: ...


class _NoOpHooks:
    """默认空操作实现 — 独立运行时使用，零开销。"""

    async def on_session_start(self, goal: str, session_id: str, context: dict) -> None:
        pass

    async def on_retrieval(self, query: str, results: list[dict], duration_ms: float) -> None:
        pass

    async def on_key_facts(self, facts: list[str]) -> None:
        pass

    async def on_response(self, session_id: str, response: str) -> None:
        pass

    async def on_session_end(self, session_id: str) -> None:
        pass


_hooks: WikiAgentHooks = _NoOpHooks()


def register_hooks(hooks: WikiAgentHooks) -> None:
    """注册外部 hooks 实现（评估平台在集成时调用）。"""
    global _hooks
    _hooks = hooks
    logger.info("[Wiki Agent] External hooks registered: %s", type(hooks).__name__)


def get_hooks() -> WikiAgentHooks:
    """获取当前 hooks 实例。"""
    return _hooks


# ── 便捷 emit 函数（业务代码调用，自动遍历已注册 hooks）────────


async def emit_session_start(goal: str, session_id: str, context: dict) -> None:
    try:
        await _hooks.on_session_start(goal, session_id, context)
    except Exception as e:
        logger.debug("Hook on_session_start error: %s", e)


async def emit_retrieval(query: str, results: list[dict], duration_ms: float) -> None:
    try:
        await _hooks.on_retrieval(query, results, duration_ms)
    except Exception as e:
        logger.debug("Hook on_retrieval error: %s", e)


async def emit_key_facts(facts: list[str]) -> None:
    try:
        await _hooks.on_key_facts(facts)
    except Exception as e:
        logger.debug("Hook on_key_facts error: %s", e)


async def emit_response(session_id: str, response: str) -> None:
    try:
        await _hooks.on_response(session_id, response)
    except Exception as e:
        logger.debug("Hook on_response error: %s", e)


async def emit_session_end(session_id: str) -> None:
    try:
        await _hooks.on_session_end(session_id)
    except Exception as e:
        logger.debug("Hook on_session_end error: %s", e)
