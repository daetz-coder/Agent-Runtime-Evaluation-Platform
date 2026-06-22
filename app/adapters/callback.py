"""
LangChain Callback Adapter - 一行代码接入，自动收集轨迹。

使用方式：
    from app.adapters.callback import create_callback_handler
    handler = create_callback_handler()
    llm = ChatZhipuAI(callbacks=[handler])

实现位于 sdk/adapters/callback.py — 此处仅做兼容性重导出。
"""

from sdk.adapters.callback import (
    create_callback_handler,
    EvalCallbackHandler,
)

__all__ = [
    "create_callback_handler",
    "EvalCallbackHandler",
]
