"""
LangChain Callback Adapter - 自动收集轨迹

设计原则：
- 标准接口：实现 LangChain BaseCallbackHandler
- 自动收集：记录 LLM 调用、工具调用/返回、失败事件
- 灵活使用：可传入 LLM 或 Agent

支持的数据源：
- LLM 调用 (llm_call)
- 工具调用 (tool_call) — on_tool_start
- 工具结果 (tool_result) — on_tool_end，独立记录
- 失败事件 (failure) — LLM/Tool/Chain 错误

使用方式：
    from sdk.adapters.callback import create_callback_handler

    # 创建 handler
    handler = create_callback_handler()

    # 传入 LLM
    llm = ChatZhipuAI(callbacks=[handler])

    # 或传入 Agent
    agent = create_agent(llm, tools, callbacks=[handler])
"""

from __future__ import annotations

import logging
import time
import traceback
from typing import Any, Dict, List
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from sdk.collector import get_collector

logger = logging.getLogger(__name__)


class EvalCallbackHandler(BaseCallbackHandler):
    """
    评估回调处理器 - 自动收集轨迹

    自动捕获：
    - on_llm_start/end: LLM 调用
    - on_tool_start/end: 工具调用
    - on_chain_start/end: 链调用
    """

    def __init__(self):
        super().__init__()
        self._collector = get_collector()
        self._pending_llm: Dict[str, Dict[str, Any]] = {}
        self._pending_tools: Dict[str, Dict[str, Any]] = {}
        self._start_times: Dict[str, float] = {}

    # ---- LLM 回调 ----

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """LLM 调用开始"""
        self._start_times[str(run_id)] = time.time()
        self._pending_llm[str(run_id)] = {
            "model": serialized.get("name", "unknown"),
            "prompts": prompts[:3],
        }

    def on_chat_model_start(
        self,
        serialized: Dict[str, Any],
        messages: List[List[Any]],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Chat 模型调用开始"""
        self._start_times[str(run_id)] = time.time()

        # 提取消息
        msg_list = []
        if messages and messages[-1]:
            for msg in messages[-1][:3]:
                if hasattr(msg, "content"):
                    msg_list.append(
                        {
                            "role": getattr(msg, "type", "unknown"),
                            "content": str(msg.content)[:200],
                        }
                    )

        self._pending_llm[str(run_id)] = {
            "model": serialized.get("name", "unknown"),
            "messages": msg_list,
        }

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """LLM 调用结束"""
        rid = str(run_id)
        start_time = self._start_times.pop(rid, time.time())
        duration_ms = (time.time() - start_time) * 1000

        pending = self._pending_llm.pop(rid, {})

        # 提取响应
        response_text = ""
        tool_calls = []
        if response.generations:
            for gen_list in response.generations:
                for gen in gen_list:
                    if hasattr(gen, "message"):
                        msg = gen.message
                        response_text = str(msg.content)[:500]
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            tool_calls = [
                                {"name": tc.get("name", ""), "args": tc.get("args", {})} for tc in msg.tool_calls
                            ]
                        break
                break

        # 记录 LLM 调用
        self._collector.record_llm_call(
            model=pending.get("model", "unknown"),
            messages=pending.get("messages", []),
            response=response_text,
            duration_ms=duration_ms,
        )

        # 记录工具调用决策
        if tool_calls:
            self._collector.record_think(f"LLM decided to call tools: {[tc['name'] for tc in tool_calls]}")

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """LLM 调用错误 — 记录 failure"""
        rid = str(run_id)
        self._pending_llm.pop(rid, None)
        self._start_times.pop(rid, None)
        self._collector.record_failure(
            error_type=type(error).__name__,
            error_message=str(error),
            context="LLM call failed",
            recoverable=True,
            stack_trace=traceback.format_exc()[-1000:],
        )

    # ---- 工具回调 ----

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """工具调用开始"""
        self._start_times[str(run_id)] = time.time()
        self._pending_tools[str(run_id)] = {
            "name": serialized.get("name", "unknown"),
            "input": input_str,
        }

    def on_tool_end(
        self,
        output: str,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """工具调用结束 — 记录 tool_call + tool_result"""
        rid = str(run_id)
        start_time = self._start_times.pop(rid, time.time())
        duration_ms = (time.time() - start_time) * 1000

        pending = self._pending_tools.pop(rid, {})
        tool_name = pending.get("name", "unknown")

        # 记录工具调用（含输出）
        self._collector.record_tool_call(
            tool_name=tool_name,
            tool_input={"raw": pending.get("input", "")},
            tool_output=output[:500] if output else None,
            duration_ms=duration_ms,
        )

        # 独立记录工具结果
        self._collector.record_tool_result(
            tool_name=tool_name,
            tool_output=output[:4000] if output else None,
            duration_ms=duration_ms,
            success=True,
        )

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """工具调用错误 — 记录 failure + tool_result(failed)"""
        rid = str(run_id)
        pending = self._pending_tools.pop(rid, None)
        self._start_times.pop(rid, None)

        tool_name = pending.get("name", "unknown") if pending else "unknown"

        self._collector.record_failure(
            error_type=type(error).__name__,
            error_message=str(error),
            context=f"Tool '{tool_name}' call failed",
            recoverable=True,
            stack_trace=traceback.format_exc()[-1000:],
        )

        # 记录失败的工具结果
        self._collector.record_tool_result(
            tool_name=tool_name,
            tool_output=str(error),
            success=False,
            error_type=type(error).__name__,
        )

    # ---- 链回调 ----

    def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """链调用开始"""
        self._start_times[str(run_id)] = time.time()

    def on_chain_end(
        self,
        outputs: Dict[str, Any],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """链调用结束"""
        rid = str(run_id)
        self._start_times.pop(rid, None)

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """链调用错误 — 记录 failure"""
        rid = str(run_id)
        self._start_times.pop(rid, None)
        self._collector.record_failure(
            error_type=type(error).__name__,
            error_message=str(error),
            context="Chain execution failed",
            recoverable=True,
            stack_trace=traceback.format_exc()[-1000:],
        )


def create_callback_handler() -> EvalCallbackHandler:
    """
    创建回调处理器

    Returns:
        回调处理器实例

    使用方式：
        from sdk.adapters.callback import create_callback_handler

        # 创建 handler
        handler = create_callback_handler()

        # 传入 LLM
        llm = ChatZhipuAI(callbacks=[handler])

        # 或传入 Agent
        agent = create_agent(llm, tools, callbacks=[handler])
    """
    return EvalCallbackHandler()
