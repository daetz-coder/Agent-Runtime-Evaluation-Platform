"""全局 Emitter — 注册 hooks 实现 + 触发事件 + 异常隔离。

提供两层接口：
- 通用层：trace(action, input, output) / step(name, detail) — 任何 Agent 都能用
- 结构化层：retrieval / tool_call / llm_call 等 — 可选，更精确的评估
"""

from __future__ import annotations

import logging
from typing import Any

from agent_hooks.defaults import NoOpHooks
from agent_hooks.protocol import AgentHooks

logger = logging.getLogger("agent_hooks")


class Emitter:
    """事件发射器。

    内部持有 hooks 实例（默认 NoOpHooks），emit 方法调用对应 hooks 方法。
    所有调用都有 try/except 保护，hooks 出错不影响 agent 主流程。
    """

    def __init__(self) -> None:
        self._hooks: AgentHooks = NoOpHooks()
        self._trace_buffer: list[dict[str, Any]] = []

    def register(self, hooks: AgentHooks) -> None:
        """注册外部 hooks 实现（评估平台在启动时调用）。"""
        self._hooks = hooks
        logger.info("Agent hooks registered: %s", type(hooks).__name__)

    @property
    def hooks(self) -> AgentHooks:
        return self._hooks

    @property
    def trace_buffer(self) -> list[dict[str, Any]]:
        """获取当前会话的 trace 缓冲（用于调试或本地分析）。"""
        return self._trace_buffer

    def clear_buffer(self) -> None:
        """清空 trace 缓冲。"""
        self._trace_buffer.clear()

    # ── 通用层：任何 Agent 都能用 ─────────────────────────

    async def trace(
        self,
        action: str,
        input: dict[str, Any] | None = None,
        output: dict[str, Any] | None = None,
        duration_ms: float | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        """通用追踪记录。

        Agent 做了任何有意义的操作都可以调用这个方法。
        action 是自由格式的类型名（如 "search", "generate", "validate", "transform"）。

        示例:
            await emit.trace("search", input={"query": "Python"}, output={"count": 5})
            await emit.trace("generate", input={"prompt": "..."}, output={"text": "..."})
            await emit.trace("validate", input={"data": ...}, output={"valid": True})
        """
        record = {
            "action": action,
            "input": input,
            "output": output,
            "duration_ms": duration_ms,
            "meta": meta,
        }
        self._trace_buffer.append(record)
        try:
            await self._hooks.on_trace(action, input, output, duration_ms, meta)
        except Exception as e:
            logger.debug("Hook on_trace error: %s", e)

    async def step(
        self,
        name: str,
        detail: str = "",
        status: str = "ok",
    ) -> None:
        """步骤记录 — 最简单的接口。

        一句话描述 Agent 做了什么。适合快速接入或简单 Agent。

        示例:
            await emit.step("检索知识库", "查询 Python 异步编程，返回 5 条结果")
            await emit.step("生成回复", "基于检索结果生成 200 字回答")
            await emit.step("执行代码", "运行 pytest，3 个测试通过", status="ok")
        """
        try:
            await self._hooks.on_step(name, detail, status)
        except Exception as e:
            logger.debug("Hook on_step error: %s", e)

    # ── 会话生命周期 ─────────────────────────────────────

    async def session_start(
        self, goal: str, session_id: str, context: dict[str, Any] | None = None
    ) -> None:
        """会话开始。clear_buffer 为新会话准备。"""
        self.clear_buffer()
        try:
            await self._hooks.on_session_start(goal, session_id, context or {})
        except Exception as e:
            logger.debug("Hook on_session_start error: %s", e)

    async def session_end(self, session_id: str) -> None:
        """会话结束。"""
        try:
            await self._hooks.on_session_end(session_id)
        except Exception as e:
            logger.debug("Hook on_session_end error: %s", e)

    # ── 结构化层：可选，更精确的评估 ─────────────────────

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
