"""
Action Type 常量定义

规范定义在 sdk/collector.py 中（SDK 作为独立包需要自包含）。
此处 re-export 供 app 层使用，避免重复定义导致不同步。
"""

from sdk.collector import ActionType

__all__ = ["ActionType"]
