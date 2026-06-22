"""
LLM Proxy Adapter - 一行代码接入，自动收集轨迹。

使用方式：
    from app.adapters import create_proxy_llm
    llm = create_proxy_llm(original_llm)

实现位于 sdk/adapters/llm_proxy.py — 此处仅做兼容性重导出。
"""

from sdk.adapters.llm_proxy import (
    create_proxy_llm,
    ProxyChatModel,
)

__all__ = [
    "create_proxy_llm",
    "ProxyChatModel",
]
