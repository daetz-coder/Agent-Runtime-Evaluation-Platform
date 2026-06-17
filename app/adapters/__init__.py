"""
Agent Evaluation Platform - Adapters Module

可插拔适配器，用于自动收集 Agent 执行轨迹。

使用方式:

    # 方式 1: LLM Proxy（适用于任何框架）
    from app.adapters import create_proxy_llm
    llm = create_proxy_llm(original_llm)

    # 方式 2: LangGraph Adapter（仅适用于 LangGraph）
    from app.adapters.langgraph import instrument_langgraph
    graph = instrument_langgraph(build_graph())

    # 方式 3: LangChain Callback（适用于 LangChain）
    from app.adapters.callback import create_callback_handler
    handler = create_callback_handler()
"""

from app.adapters.llm_proxy import create_proxy_llm
from app.adapters.callback import create_callback_handler

__all__ = [
    "create_proxy_llm",
    "create_callback_handler",
]

# LangGraph adapter 需要单独导入（因为是可选依赖）
try:
    from app.adapters.langgraph import instrument_langgraph
    __all__.append("instrument_langgraph")
except ImportError:
    pass
