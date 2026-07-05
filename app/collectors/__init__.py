"""
Data collectors for trajectory collection.

TrajectoryCollector lives in sdk/collector.py (single implementation).
All agents use HTTP mode to push trajectory data to the evaluation platform.
"""

from sdk.collector import ActionType, TrajectoryCollector, get_collector, reset_collector

__all__ = [
    "TrajectoryCollector",
    "get_collector",
    "reset_collector",
    "ActionType",
]
