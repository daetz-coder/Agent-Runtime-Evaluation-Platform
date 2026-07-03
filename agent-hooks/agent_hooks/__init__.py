"""agent-hooks — Agent 生命周期钩子 SDK。

轻量、零依赖的 agent 评估接入方案。

Agent 项目使用:
    from agent_hooks import emit

    await emit.session_start(goal, session_id, context)
    await emit.retrieval(query, results, duration_ms)
    await emit.response(session_id, response)
    await emit.session_end(session_id)

评估平台注册:
    from agent_hooks import AgentHooks, register

    class EvalHooks(AgentHooks):
        async def on_retrieval(self, query, results, duration_ms):
            ...

    register(EvalHooks())
"""

from agent_hooks.defaults import NoOpHooks
from agent_hooks.emitter import Emitter
from agent_hooks.protocol import AgentHooks

__version__ = "0.1.0"

__all__ = [
    "AgentHooks",
    "Emitter",
    "NoOpHooks",
    "emit",
    "register",
]

# 全局 emitter 实例（模块级单例）
emit = Emitter()


def register(hooks: AgentHooks) -> None:
    """注册 hooks 实现（评估平台调用）。"""
    emit.register(hooks)
