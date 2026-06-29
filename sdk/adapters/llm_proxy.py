"""
LLM Proxy Adapter - 代理 LLM 调用，自动收集轨迹

设计原则：
- 透明代理：包装原始 LLM，保持相同接口
- 自动收集：自动记录输入输出
- 零侵入：不需要修改原有代码

支持的数据源：
- LLM 调用 (llm_call)
- 工具决策 (think) — LLM 返回 tool_calls 时记录
- 工具调用 (tool_call) — LLM 返回 tool_calls 时记录

使用方式：
    from app.adapters import create_proxy_llm

    # 原来的代码
    llm = ChatZhipuAI(...)

    # 替换为
    llm = create_proxy_llm(ChatZhipuAI(...))

    # 后续使用完全相同
    response = llm.invoke("Hello")
"""

from __future__ import annotations

import logging
import time
from typing import Any, AsyncIterator, List, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatGenerationChunk, ChatResult

from sdk.collector import get_collector

logger = logging.getLogger(__name__)


class ProxyChatModel(BaseChatModel):
    """
    代理聊天模型 - 包装原始 LLM，自动收集轨迹

    这是一个透明代理，会：
    1. 转发所有调用到原始 LLM
    2. 自动记录输入输出
    3. 计算耗时
    """

    _original_llm: BaseChatModel
    _collector: Any

    def __init__(self, original_llm: BaseChatModel, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, "_original_llm", original_llm)
        object.__setattr__(self, "_collector", get_collector())

    @property
    def _llm_type(self) -> str:
        return f"proxy-{self._original_llm._llm_type}"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        """同步生成 - 代理到原始 LLM"""
        start_time = time.time()

        # 调用原始 LLM
        result = self._original_llm._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

        # 记录调用
        duration_ms = (time.time() - start_time) * 1000
        self._record_call(messages, result, duration_ms)

        return result

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        """异步生成 - 代理到原始 LLM

        ⚠️ 强制 stream=False 防止原始 LLM 的 streaming=True 泄露到 API，
        导致返回 AsyncStream 而非 ChatCompletion。
        """
        start_time = time.time()

        # 强制非流式 — 流式走 _astream 路径
        kwargs.pop("streaming", None)
        kwargs.pop("stream", None)
        kwargs["stream"] = False
        result = await self._original_llm._agenerate(
            messages, stop=stop, run_manager=run_manager, **kwargs
        )

        # 记录调用
        duration_ms = (time.time() - start_time) * 1000
        self._record_call(messages, result, duration_ms)

        return result

    async def _astream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        """流式生成 — 透传并在结束后记录完整回复。"""
        start_time = time.time()
        collected: list[str] = []

        async for chunk in self._original_llm._astream(
            messages, stop=stop, run_manager=run_manager, **kwargs
        ):
            text = ""
            if hasattr(chunk, "message") and chunk.message is not None:
                text = str(getattr(chunk.message, "content", "") or "")
            elif hasattr(chunk, "text"):
                text = str(chunk.text or "")
            if text:
                collected.append(text)
            yield chunk

        if collected:
            duration_ms = (time.time() - start_time) * 1000
            self._record_stream_call(messages, "".join(collected), duration_ms)

    def _record_stream_call(
        self,
        messages: List[BaseMessage],
        response_text: str,
        duration_ms: float,
    ) -> None:
        """Record aggregated streaming LLM output for trajectory collection."""
        try:
            msg_list = []
            for msg in messages:
                if hasattr(msg, "content"):
                    msg_list.append(
                        {
                            "role": getattr(msg, "type", "unknown"),
                            "content": str(msg.content)[:200],
                        }
                    )
            self._collector.record_llm_call(
                model=self._llm_type,
                messages=msg_list,
                response=response_text[:500],
                duration_ms=duration_ms,
            )
        except Exception as e:
            logger.warning("Failed to record streaming LLM call: %s", e)

    def _record_call(
        self,
        messages: List[BaseMessage],
        result: ChatResult,
        duration_ms: float,
    ):
        """记录 LLM 调用 + 工具决策 + 工具调用"""
        try:
            # 提取消息内容
            msg_list = []
            for msg in messages:
                if hasattr(msg, "content"):
                    msg_list.append(
                        {
                            "role": getattr(msg, "type", "unknown"),
                            "content": str(msg.content)[:200],
                        }
                    )

            # 提取响应内容
            response_text = ""
            if result.generations:
                for gen in result.generations:
                    if gen and hasattr(gen[0], "message"):
                        response_text = str(gen[0].message.content)[:500]
                        break

            # 提取工具调用
            tool_calls = []
            if result.generations:
                for gen in result.generations:
                    if gen and hasattr(gen[0], "message"):
                        msg = gen[0].message
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            for tc in msg.tool_calls:
                                tool_calls.append(
                                    {
                                        "name": tc.get("name", ""),
                                        "args": tc.get("args", {}),
                                    }
                                )

            # 记录到收集器
            self._collector.record_llm_call(
                model=self._llm_type,
                messages=msg_list,
                response=response_text,
                duration_ms=duration_ms,
            )

            # 如果有工具调用，记录工具决策 + 工具调用
            if tool_calls:
                tool_names = [tc["name"] for tc in tool_calls]
                self._collector.record_think(f"LLM decided to call tools: {tool_names}")

                # 为每个工具调用记录独立的 tool_call
                for tc in tool_calls:
                    self._collector.record_tool_call(
                        tool_name=tc["name"],
                        tool_input=tc["args"],
                    )

        except Exception as e:
            logger.warning(f"Failed to record LLM call: {e}")

    def bind_tools(self, tools: List[Any], **kwargs: Any) -> Any:
        """绑定工具 - 代理到原始 LLM"""
        return self._original_llm.bind_tools(tools, **kwargs)

    def __getattr__(self, name: str) -> Any:
        """转发所有其他属性到原始 LLM，避免递归"""
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._original_llm, name)


def create_proxy_llm(llm: BaseChatModel) -> BaseChatModel:
    """
    创建代理 LLM

    Args:
        llm: 原始 LLM 实例

    Returns:
        代理 LLM 实例（透明包装）

    使用方式：
        from app.adapters import create_proxy_llm

        # 原来的代码
        llm = ChatZhipuAI(...)

        # 替换为
        llm = create_proxy_llm(ChatZhipuAI(...))

        # 后续使用完全相同
        response = llm.invoke("Hello")
    """
    # 如果已经是代理，直接返回
    if isinstance(llm, ProxyChatModel):
        return llm

    return ProxyChatModel(original_llm=llm)
