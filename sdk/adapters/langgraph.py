"""
LangGraph Adapter - 包装 LangGraph，自动收集轨迹

设计原则：
- 一行替换：graph = instrument_langgraph(build_graph())
- 完全透明：保持原有接口
- 自动收集：记录节点执行、状态变化、工具调用、失败事件

支持的数据源：
- 节点执行 (node_execute)
- 状态变化 (state_change) — 节点执行前后自动记录 diff
- 工具调用 (tool_call) / 工具决策 (tool_decision)
- 失败事件 (failure) — 节点异常时自动记录

使用方式：
    from sdk.adapters.langgraph import instrument_langgraph

    # 原来的代码
    graph = build_graph()

    # 替换为
    graph = instrument_langgraph(build_graph())

    # 后续使用完全相同
    result = await graph.ainvoke(initial_state)
"""

from __future__ import annotations

import inspect
import logging
import time
import traceback
from typing import Any, Callable, Dict, Union

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph, StateGraph

from sdk.collector import ActionType, get_collector

logger = logging.getLogger(__name__)


def _accepts_config(node_func: Callable) -> bool:
    """Return True if node accepts LangGraph RunnableConfig."""
    return "config" in inspect.signature(node_func).parameters


def _call_node(node_func: Callable, state: Any, config: RunnableConfig | None) -> Any:
    """Invoke a sync node, forwarding config when supported."""
    if _accepts_config(node_func):
        return node_func(state, config)
    return node_func(state)


async def _call_node_async(
    node_func: Callable, state: Any, config: RunnableConfig | None
) -> Any:
    """Invoke an async node, forwarding config when supported."""
    if _accepts_config(node_func):
        return await node_func(state, config)
    return await node_func(state)


class InstrumentedStateGraph:
    """
    包装 StateGraph - 自动收集节点执行轨迹

    这是一个透明包装器，会：
    1. 包装所有节点函数
    2. 记录节点输入输出
    3. 记录状态变化
    4. 保持原有接口
    """

    def __init__(self, original_graph: StateGraph):
        self._original = original_graph
        self._collector = get_collector()
        self._instrumented_nodes: Dict[str, Callable] = {}

        # 包装已添加的节点
        self._instrument_existing_nodes()

    def _instrument_existing_nodes(self):
        """包装已添加的节点的 runnable"""
        if hasattr(self._original, "nodes"):
            for node_name, spec in self._original.nodes.items():
                if node_name not in self._instrumented_nodes:
                    self._wrap_spec_runnable(node_name, spec)
                    self._instrumented_nodes[node_name] = True

    def _wrap_spec_runnable(self, node_name: str, spec):
        """替换 StateNodeSpec 中的 runnable 为包装后的版本"""
        original = spec.runnable
        # 提取原始 callable（可能被 langgraph 包装过）
        inner = getattr(original, "func", None) or original
        wrapped = self._wrap_node(node_name, inner)
        # 如果 original 是 RunnableCallable 类型，替换其 func
        if hasattr(original, "func"):
            original.func = wrapped
        else:
            spec.runnable = wrapped

    def add_node(self, node_name: str, node_func: Callable, **kwargs) -> "InstrumentedStateGraph":
        """添加节点 — 先让 StateGraph 创建 Spec，再包装 runnable"""
        self._original.add_node(node_name, node_func, **kwargs)
        spec = self._original.nodes[node_name]
        self._wrap_spec_runnable(node_name, spec)
        self._instrumented_nodes[node_name] = True
        return self

    def _wrap_node(self, node_name: str, node_func: Callable) -> Callable:
        """包装单个节点 — 自动记录 node_execute / state_change / failure

        自动检测原始节点是否为 async，使用对应的同步/异步包装器。
        """
        if inspect.iscoroutinefunction(node_func):
            return self._wrap_node_async(node_name, node_func)
        else:
            return self._wrap_node_sync(node_name, node_func)

    def _wrap_node_sync(self, node_name: str, node_func: Callable) -> Callable:
        """同步节点包装器"""
        import functools

        @functools.wraps(node_func)
        def wrapper(state, config: RunnableConfig | None = None, **kwargs):
            start_time = time.time()
            state_before = self._extract_state_summary(state)

            self._collector.record_node_execute(
                node_name=node_name,
                input_data=state_before,
            )

            try:
                result = _call_node(node_func, state, config)
                duration_ms = (time.time() - start_time) * 1000

                state_after = self._extract_result_summary(result)

                self._collector.record_node_execute(
                    node_name=f"{node_name}_complete",
                    output_data=state_after,
                )
                self._collector.record_state_change(
                    state_before=state_before,
                    state_after=state_after,
                    trigger=node_name,
                    node_name=node_name,
                )
                self._extract_tool_calls(node_name, state, result)
                return result

            except Exception as e:
                self._collector.record_failure(
                    error_type=type(e).__name__,
                    error_message=str(e),
                    context=f"Node {node_name} execution failed",
                    recoverable=True,
                    node_name=node_name,
                    stack_trace=traceback.format_exc()[-1000:],
                )
                raise

        return wrapper

    def _wrap_node_async(self, node_name: str, node_func: Callable) -> Callable:
        """异步节点包装器"""
        import functools

        @functools.wraps(node_func)
        async def async_wrapper(
            state: Dict[str, Any],
            config: RunnableConfig | None = None,
            **kwargs: Any,
        ) -> Dict[str, Any]:
            start_time = time.time()
            state_before = self._extract_state_summary(state)

            self._collector.record_node_execute(
                node_name=node_name,
                input_data=state_before,
            )

            try:
                result = await _call_node_async(node_func, state, config)
                duration_ms = (time.time() - start_time) * 1000

                state_after = self._extract_result_summary(result)

                self._collector.record_node_execute(
                    node_name=f"{node_name}_complete",
                    output_data=state_after,
                )
                self._collector.record_state_change(
                    state_before=state_before,
                    state_after=state_after,
                    trigger=node_name,
                    node_name=node_name,
                )
                self._extract_tool_calls(node_name, state, result)
                return result

            except Exception as e:
                self._collector.record_failure(
                    error_type=type(e).__name__,
                    error_message=str(e),
                    context=f"Node {node_name} execution failed",
                    recoverable=True,
                    node_name=node_name,
                    stack_trace=traceback.format_exc()[-1000:],
                )
                raise

        async_wrapper.__name__ = getattr(node_func, "__name__", node_name)
        async_wrapper.__doc__ = getattr(node_func, "__doc__", None)
        return async_wrapper

    def _extract_state_summary(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """提取状态摘要（避免序列化过大对象）"""
        summary = {}
        for key, value in state.items():
            if key == "messages":
                # 只记录消息数量和最后一条
                messages = value if isinstance(value, list) else []
                summary["messages_count"] = len(messages)
                if messages:
                    last_msg = messages[-1]
                    if hasattr(last_msg, "content"):
                        summary["last_message"] = str(last_msg.content)[:100]
            elif isinstance(value, (str, int, float, bool)):
                summary[key] = value
            else:
                summary[key] = f"<{type(value).__name__}>"
        return summary

    def _extract_result_summary(self, result: Any) -> Dict[str, Any]:
        """提取结果摘要"""
        if not isinstance(result, dict):
            return {"result": str(result)[:200]}

        summary = {}
        for key, value in result.items():
            if key == "messages":
                messages = value if isinstance(value, list) else []
                summary["new_messages_count"] = len(messages)
                # 提取 AI 消息内容
                for msg in messages:
                    if isinstance(msg, AIMessage):
                        summary["ai_response"] = str(msg.content)[:200]
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            summary["tool_calls"] = [
                                {"name": tc.get("name", ""), "args": str(tc.get("args", {}))[:50]}
                                for tc in msg.tool_calls
                            ]
                        break
            elif isinstance(value, (str, int, float, bool)):
                summary[key] = value
        return summary

    def _extract_tool_calls(
        self,
        node_name: str,
        state: Dict[str, Any],
        result: Dict[str, Any],
    ):
        """提取并记录工具调用决策 + 工具结果"""
        if not isinstance(result, dict) or "messages" not in result:
            return

        messages = result["messages"]
        if not isinstance(messages, list):
            return

        for msg in messages:
            if not isinstance(msg, AIMessage) or not hasattr(msg, "tool_calls"):
                continue
            if not msg.tool_calls:
                continue

            for tc in msg.tool_calls:
                tool_name = tc.get("name", "unknown")
                tool_input = tc.get("args", {})

                # 记录工具选择决策
                self._collector.record(
                    action_type=ActionType.TOOL_DECISION,
                    action_detail={
                        "node_name": node_name,
                        "tool_name": tool_name,
                        "input": tool_input,
                    },
                )

                # 记录工具调用
                self._collector.record_tool_call(
                    tool_name=tool_name,
                    tool_input=tool_input,
                )

    def __getattr__(self, name: str) -> Any:
        """转发所有其他属性到原始图"""
        return getattr(self._original, name)

    def compile(self, **kwargs: Any) -> CompiledStateGraph:
        """编译图"""
        return self._original.compile(**kwargs)


class InstrumentedCompiledGraph:
    """
    包装 CompiledStateGraph - 自动收集执行轨迹
    """

    def __init__(self, original_graph: CompiledStateGraph):
        self._original = original_graph
        self._collector = get_collector()

    async def ainvoke(self, input: Any, config: Any = None, **kwargs: Any) -> Any:
        """异步调用 - 包装原始调用"""
        start_time = time.time()

        # 记录开始
        self._collector.record_think("Graph execution started")

        # 调用原始图
        try:
            result = await self._original.ainvoke(input, config=config, **kwargs)
        except Exception as e:
            self._collector.record_failure(
                error_type=type(e).__name__,
                error_message=str(e),
                context="Graph ainvoke failed",
                recoverable=False,
                stack_trace=traceback.format_exc()[-1000:],
            )
            raise

        # 记录完成
        duration_ms = (time.time() - start_time) * 1000
        self._collector.record_think(f"Graph execution completed in {duration_ms:.0f}ms")

        return result

    def invoke(self, input: Any, config: Any = None, **kwargs: Any) -> Any:
        """同步调用 - 包装原始调用"""
        start_time = time.time()

        # 记录开始
        self._collector.record_think("Graph execution started")

        # 调用原始图
        try:
            result = self._original.invoke(input, config=config, **kwargs)
        except Exception as e:
            self._collector.record_failure(
                error_type=type(e).__name__,
                error_message=str(e),
                context="Graph invoke failed",
                recoverable=False,
                stack_trace=traceback.format_exc()[-1000:],
            )
            raise

        # 记录完成
        duration_ms = (time.time() - start_time) * 1000
        self._collector.record_think(f"Graph execution completed in {duration_ms:.0f}ms")

        return result

    def __getattr__(self, name: str) -> Any:
        """转发所有其他属性到原始图"""
        return getattr(self._original, name)


def instrument_langgraph(graph: Union[StateGraph, CompiledStateGraph]) -> Union[StateGraph, CompiledStateGraph]:
    """
    包装 LangGraph 图，自动收集轨迹

    Args:
        graph: 原始 StateGraph 或 CompiledStateGraph

    Returns:
        包装后的图（透明包装）

    使用方式：
        from sdk.adapters.langgraph import instrument_langgraph

        # 原来的代码
        graph = build_graph()

        # 替换为
        graph = instrument_langgraph(build_graph())

        # 后续使用完全相同
        result = await graph.ainvoke(initial_state)
    """
    # 如果是已编译的图
    if isinstance(graph, CompiledStateGraph):
        return InstrumentedCompiledGraph(graph)

    # 如果是未编译的图
    if isinstance(graph, StateGraph):
        return InstrumentedStateGraph(graph)

    # 如果都不是，返回原图
    logger.warning(f"Unsupported graph type: {type(graph)}")
    return graph
