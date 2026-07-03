"""wiki-agent 生命周期钩子 — 委托给 agent-hooks SDK。

wiki-agent 业务代码通过此模块的 emit_* 函数触发事件。
默认空操作，评估平台通过 agent-hooks 的 register() 注入实现。
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# 尝试导入 agent-hooks SDK，不可用时降级为空操作
try:
    from agent_hooks import emit as _emit
    _HAS_SDK = True
except ImportError:
    _HAS_SDK = False
    logger.info("[Wiki Agent] agent-hooks not installed — hooks disabled")

    class _NoOpEmit:
        """降级空操作 emitter。"""
        def __getattr__(self, name: str):
            async def _noop(*args, **kwargs):
                pass
            return _noop

    _emit = _NoOpEmit()


# ── 便捷函数（业务代码调用，保持向后兼容）────────────────


async def emit_session_start(goal: str, session_id: str, context: dict) -> None:
    await _emit.session_start(goal, session_id, context)


async def emit_retrieval(query: str, results: list[dict], duration_ms: float) -> None:
    await _emit.retrieval(query, results, duration_ms)


async def emit_key_facts(facts: list[str]) -> None:
    await _emit.key_facts(facts, scope="session")


async def emit_response(session_id: str, response: str) -> None:
    await _emit.response(session_id, response)


async def emit_session_end(session_id: str) -> None:
    await _emit.session_end(session_id)
