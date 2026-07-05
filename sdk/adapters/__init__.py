"""
sdk.adapters — SDK 适配器层入口

提供三种 Agent 框架的轨迹采集适配器：

| 适配器            | 适用框架      | 集成方式         |
|-------------------|--------------|------------------|
| langgraph         | LangGraph    | 替换一行 graph   |
| llm_proxy         | LangChain 系 | 替换 LLM 创建    |
| callback          | LangChain 系 | 注入 handler     |

所有适配器内部都通过 get_collector() 获取 TrajectoryCollector 单例，
将采集到的轨迹数据统一推送到评估平台。
"""

from sdk.adapters.callback import EvalCallbackHandler, create_callback_handler
from sdk.adapters.langgraph import InstrumentedStateGraph, instrument_langgraph
from sdk.adapters.llm_proxy import ProxyChatModel, create_proxy_llm

__all__ = [
    "instrument_langgraph",
    "InstrumentedStateGraph",
    "create_proxy_llm",
    "ProxyChatModel",
    "create_callback_handler",
    "EvalCallbackHandler",
]
