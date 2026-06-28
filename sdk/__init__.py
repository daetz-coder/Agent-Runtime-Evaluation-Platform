"""
Agent Eval SDK — 零侵入 Agent 运行时轨迹收集。

使用方式：
    from agent_eval_sdk import instrument_langgraph, create_proxy_llm, create_callback_handler

    # 方式 1: LangGraph
    from agent_eval_sdk import instrument_langgraph
    graph = instrument_langgraph(build_graph())

    # 方式 2: LLM Proxy
    from agent_eval_sdk import create_proxy_llm
    llm = create_proxy_llm(original_llm)

    # 方式 3: LangChain Callback
    from agent_eval_sdk import create_callback_handler
    handler = create_callback_handler()
    llm = ChatZhipuAI(callbacks=[handler])

配置（可选，通过环境变量）：
    EVAL_API_BASE_URL  — 评估平台地址（默认 http://127.0.0.1:8000）
    EVAL_ENABLED       — 是否启用收集（默认 true）
    EVAL_BATCH_SIZE    — 批量上传大小（默认 10）
"""

from sdk.adapters.callback import EvalCallbackHandler, create_callback_handler
from sdk.adapters.langgraph import InstrumentedStateGraph, instrument_langgraph
from sdk.adapters.llm_proxy import ProxyChatModel, create_proxy_llm
from sdk.collector import ActionType, TrajectoryCollector, get_collector

__version__ = "0.1.0"

__all__ = [
    # Adapters
    "instrument_langgraph",
    "InstrumentedStateGraph",
    "create_proxy_llm",
    "ProxyChatModel",
    "create_callback_handler",
    "EvalCallbackHandler",
    # Collector
    "TrajectoryCollector",
    "get_collector",
    "ActionType",
]
