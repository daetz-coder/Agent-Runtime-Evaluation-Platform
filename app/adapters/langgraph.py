"""
LangGraph Adapter - 一行代码接入，自动收集轨迹。

使用方式：
    from app.adapters.langgraph import instrument_langgraph
    graph = instrument_langgraph(build_graph())

实现位于 sdk/adapters/langgraph.py — 此处仅做兼容性重导出。
"""

from sdk.adapters.langgraph import (
    InstrumentedCompiledGraph,
    InstrumentedStateGraph,
    instrument_langgraph,
)

__all__ = [
    "instrument_langgraph",
    "InstrumentedStateGraph",
    "InstrumentedCompiledGraph",
]
