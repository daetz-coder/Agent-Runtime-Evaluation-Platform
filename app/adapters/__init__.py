"""
Agent Evaluation Platform - Adapters Module

可插拔适配器，用于自动收集 Agent 执行轨迹。
实际实现位于 sdk/ 包中。

使用方式:

    # 方式 1: LLM Proxy（适用于任何框架）
    from app.adapters import create_proxy_llm
    llm = create_proxy_llm(original_llm)

    # 方式 2: LangGraph Adapter（仅适用于 LangGraph）
    from app.adapters import instrument_langgraph
    graph = instrument_langgraph(build_graph())

    # 方式 3: LangChain Callback（适用于 LangChain）
    from app.adapters import create_callback_handler
    handler = create_callback_handler()

    # 外部项目也可直接使用 SDK:
    #   pip install httpx
    #   export PYTHONPATH=/path/to/project
    #   from sdk import instrument_langgraph, create_proxy_llm
"""

from sdk.adapters.callback import EvalCallbackHandler, create_callback_handler
from sdk.adapters.llm_proxy import ProxyChatModel, create_proxy_llm

__all__ = [
    "create_proxy_llm",
    "ProxyChatModel",
    "create_callback_handler",
    "EvalCallbackHandler",
]

# LangGraph adapter 需要单独导入（因为是可选依赖）
try:
    from sdk.adapters.langgraph import InstrumentedStateGraph, instrument_langgraph

    __all__.extend(["instrument_langgraph", "InstrumentedStateGraph"])
except ImportError:
    pass
