"""agent-hooks — Agent 生命周期钩子 SDK。

轻量、零依赖的 agent 评估接入方案。提供两层接口：

通用层（任何 Agent 都能用）:
    from agent_hooks import emit

    await emit.trace("search", input={"query": "..."}, output={"results": [...]})
    await emit.step("检索知识库", "返回 5 条结果")

结构化层（可选，更精确的评估）:
    await emit.retrieval(query, results, duration_ms)
    await emit.tool_call("search", args, result, duration_ms)
    await emit.llm_call(model, messages, response)

会话生命周期:
    await emit.session_start(goal, session_id, context)
    await emit.session_end(session_id)

评估平台注册:
    from agent_hooks import AgentHooks, register

    class EvalHooks(AgentHooks):
        async def on_retrieval(self, query, results, duration_ms):
            ...
        async def on_trace(self, action, input, output, duration_ms, meta):
            ...

    register(EvalHooks())
"""

from agent_hooks.defaults import NoOpHooks
from agent_hooks.emitter import Emitter
from agent_hooks.protocol import AgentHooks

__version__ = "0.2.0"

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
