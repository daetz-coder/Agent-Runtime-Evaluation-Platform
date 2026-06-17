"""
TrajectoryCollector - Manages step numbering, timestamps, and local trajectory cache.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agent_eval_sdk.models import TrajectoryStep


class TrajectoryCollector:
    """
    Trajectory Collector.

    Responsibilities:
    - Maintain auto-incrementing step_number
    - Timestamp each step
    - Cache trajectory in memory (optional export)

    Thread-safe: Uses lock to protect step_counter for multi-threaded agents.
    """

    def __init__(self):
        self._step_counter: int = 0
        self._steps: List[TrajectoryStep] = []
        self._lock = threading.Lock()

    @property
    def current_step(self) -> int:
        return self._step_counter

    @property
    def steps(self) -> List[TrajectoryStep]:
        """Return read-only copy of trajectory."""
        with self._lock:
            return list(self._steps)

    def add_step(
        self,
        action_type: str,
        action_detail: Dict[str, Any],
        observation: Optional[str] = None,
        step_number: Optional[int] = None,
        timestamp: Optional[datetime] = None,
    ) -> TrajectoryStep:
        """
        Add a trajectory step.

        Args:
            action_type: Action type ("plan", "tool_call", "think", "replan")
            action_detail: Action detail dict
            observation: Optional observation result
            step_number: Optional override for step number (default: auto-increment)
            timestamp: Optional timestamp (default: current UTC time)

        Returns:
            Created TrajectoryStep
        """
        with self._lock:
            if step_number is None:
                self._step_counter += 1
                step_number = self._step_counter
            else:
                self._step_counter = max(self._step_counter, step_number)

            step = TrajectoryStep(
                step_number=step_number,
                action_type=action_type,
                action_detail=action_detail,
                observation=observation,
                timestamp=timestamp or datetime.now(timezone.utc),
            )

            self._steps.append(step)
            return step

    def get_trajectory(self) -> List[Dict[str, Any]]:
        """Export trajectory as API-compatible dict list."""
        with self._lock:
            return [step.model_dump_for_api() for step in self._steps]

    def reset(self) -> None:
        """Reset collector state."""
        with self._lock:
            self._step_counter = 0
            self._steps.clear()
