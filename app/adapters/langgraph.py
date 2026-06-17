"""
LangGraph Adapter - 包装 LangGraph，自动收集轨迹

设计原则：
- 一行替换：graph = instrument_langgraph(build_graph())
- 完全透明：保持原有接口
- 自动收集：记录节点执行、状态变化、工具调用

使用方式：
    from app.adapters.langgraph import instrument_langgraph

    # 原来的代码
    graph = build_graph()

    # 替换为
    graph = instrument_langgraph(build_graph())

    # 后续使用完全相同
    result = await graph.ainvoke(initial_state)
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

from langchain_core.messages import AIMessage, BaseMessage
from langgraph.graph.state import CompiledStateGraph, StateGraph

from app.collectors.trajectory import get_collector

logger = logging.getLogger(__name__)


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
        """包装已添加的节点"""
        # StateGraph 的节点存储在 .nodes 属性中
        if hasattr(self._original, 'nodes'):
            for node_name, node_func in self._original.nodes.items():
                self._original.nodes[node_name] = self._wrap_node(node_name, node_func)

    def _wrap_node(self, node_name: str, node_func: Callable) -> Callable:
        """包装单个节点"""
        def wrapper(state: Dict[str, Any]) -> Dict[str, Any]:
            start_time = time.time()

            # 记录节点开始
            self._collector.record_node_execute(
                node_name=node_name,
                input_data=self._extract_state_summary(state),
            )

            # 执行原始节点
            try:
                result = node_func(state)
                duration_ms = (time.time() - start_time) * 1000

                # 记录节点完成
                self._collector.record_node_execute(
                    node_name=f"{node_name}_complete",
                    output_data=self._extract_result_summary(result),
                )

                # 记录工具调用（如果有）
                self._extract_tool_calls(node_name, state, result)

                return result

            except Exception as e:
                # 记录错误
                self._collector.record_think(f"Node {node_name} failed: {e}")
                raise

        # 保留原始函数的属性
        wrapper.__name__ = getattr(node_func, '__name__', node_name)
        wrapper.__doc__ = getattr(node_func, '__doc__', None)

        return wrapper

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
                    if hasattr(last_msg, 'content'):
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
                        if hasattr(msg, 'tool_calls') and msg.tool_calls:
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
        """提取并记录工具调用"""
        # 检查结果中的工具调用
        if isinstance(result, dict) and "messages" in result:
            messages = result["messages"]
            if isinstance(messages, list):
                for msg in messages:
                    if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls'):
                        if msg.tool_calls:
                            for tc in msg.tool_calls:
                                self._collector.record_tool_call(
                                    tool_name=tc.get("name", "unknown"),
                                    tool_input=tc.get("args", {}),
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
        self._collector.record_think(f"Graph execution started")

        # 调用原始图
        result = await self._original.ainvoke(input, config=config, **kwargs)

        # 记录完成
        duration_ms = (time.time() - start_time) * 1000
        self._collector.record_think(
            f"Graph execution completed in {duration_ms:.0f}ms"
        )

        return result

    def invoke(self, input: Any, config: Any = None, **kwargs: Any) -> Any:
        """同步调用 - 包装原始调用"""
        start_time = time.time()

        # 记录开始
        self._collector.record_think(f"Graph execution started")

        # 调用原始图
        result = self._original.invoke(input, config=config, **kwargs)

        # 记录完成
        duration_ms = (time.time() - start_time) * 1000
        self._collector.record_think(
            f"Graph execution completed in {duration_ms:.0f}ms"
        )

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
        from app.adapters.langgraph import instrument_langgraph

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
