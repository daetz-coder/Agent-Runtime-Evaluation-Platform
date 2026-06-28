"""
Data collectors for trajectory collection.
实际实现位于 sdk/collector.py 中。
"""

from sdk.collector import ActionType, TrajectoryCollector, get_collector, reset_collector

__all__ = [
    "TrajectoryCollector",
    "get_collector",
    "reset_collector",
    "ActionType",
]
