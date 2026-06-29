"""
Data collectors for trajectory collection.

TrajectoryCollector lives in sdk/collector.py (single implementation).
Wiki Agent uses app/collectors/inprocess_transport.py for same-process DB writes.
"""

from sdk.collector import ActionType, TrajectoryCollector, get_collector, reset_collector

__all__ = [
    "TrajectoryCollector",
    "get_collector",
    "reset_collector",
    "ActionType",
]
