"""
AgentTracker - SDK main tracker, coordinates Collector and Reporter.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agent_eval_sdk.config import SDKConfig
from agent_eval_sdk.core.collector import TrajectoryCollector
from agent_eval_sdk.core.reporter import AsyncReporter
from agent_eval_sdk.exceptions import SDKError, TaskNotCreatedError
from agent_eval_sdk.models import (
    ActionType,
    TaskCreate,
    TrajectoryStep,
)

logger = logging.getLogger("agent_eval_sdk")


class AgentTracker:
    """
    Agent Tracker - SDK Core Class.

    Responsibilities:
    - Manage task lifecycle (create, complete)
    - Coordinate trajectory collection (Collector) and async reporting (Reporter)
    - Provide manual API for recording steps
    - Support context manager usage

    Usage:
        # Method 1: Manual API
        tracker = AgentTracker(config)
        tracker.start_task(goal="...", context={...})
        tracker.record_plan(plan={...})
        tracker.record_tool_call(name="search", input={...}, output="...")
        tracker.complete_task()

        # Method 2: Context Manager
        with AgentTracker(config, goal="...", context={...}) as tracker:
            tracker.record_plan(plan={...})
            ...
        # auto complete_task + flush on exit
    """

    def __init__(
        self,
        config: Optional[SDKConfig] = None,
        goal: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        task_id: Optional[str] = None,
    ):
        self._config = config or SDKConfig()
        self._task_id: Optional[str] = task_id
        self._goal: Optional[str] = goal
        self._context: Optional[Dict[str, Any]] = context
        self._is_active: bool = False

        # Initialize sub-components
        self._collector = TrajectoryCollector()
        self._reporter = AsyncReporter(self._config)

    @property
    def task_id(self) -> Optional[str]:
        return self._task_id

    @property
    def is_active(self) -> bool:
        return self._is_active

    # ---- Task Lifecycle ----

    def start_task(
        self,
        goal: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Start tracking a new task.

        Returns:
            task_id: Newly created task ID
        """
        if self._is_active:
            raise SDKError("Tracker is already active. Call complete_task() first.")

        self._goal = goal or self._goal
        self._context = context or self._context

        if not self._goal:
            raise ValueError("goal is required")

        # Synchronously create backend task
        task_data = TaskCreate(goal=self._goal, context=self._context)
        response = self._reporter.create_task_sync(task_data)
        self._task_id = response.id

        # Start async reporter
        self._reporter.start(self._task_id)
        self._is_active = True
        self._collector.reset()

        logger.info(f"Task started: {self._task_id}")
        return self._task_id

    def complete_task(self) -> Optional[str]:
        """
        Mark task complete. Flush all pending data, stop reporter.

        Returns:
            evaluation_id: If auto_run_evaluation=True, return evaluation ID
        """
        if not self._is_active:
            logger.warning("complete_task called but tracker is not active")
            return None

        # Flush remaining data
        self._reporter.flush()
        self._reporter.stop()

        # Mark backend task complete
        self._reporter.mark_task_complete_sync(self._task_id)

        eval_id = None
        if self._config.auto_run_evaluation:
            eval_resp = self._reporter.run_evaluation_sync(self._task_id)
            eval_id = eval_resp.id

        self._is_active = False
        logger.info(f"Task completed: {self._task_id}")
        return eval_id

    # ---- Context Manager ----

    def __enter__(self) -> "AgentTracker":
        self.start_task(self._goal, self._context)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        try:
            self.complete_task()
        except Exception:
            logger.exception("Error during tracker cleanup")

    async def __aenter__(self) -> "AgentTracker":
        self.start_task(self._goal, self._context)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        try:
            self.complete_task()
        except Exception:
            logger.exception("Error during tracker cleanup")

    # ---- Manual Recording API ----

    def record_plan(self, plan: Dict[str, Any]) -> TrajectoryStep:
        """Record a planning step."""
        return self._add_step(
            action_type=ActionType.PLAN,
            action_detail=plan,
        )

    def record_tool_call(
        self,
        name: str,
        input: Dict[str, Any],
        output: Optional[str] = None,
    ) -> TrajectoryStep:
        """Record a tool call step."""
        return self._add_step(
            action_type=ActionType.TOOL_CALL,
            action_detail={"tool_name": name, "input": input},
            observation=output,
        )

    def record_think(self, thought: str) -> TrajectoryStep:
        """Record a thinking step."""
        return self._add_step(
            action_type=ActionType.THINK,
            action_detail={"thought": thought},
        )

    def record_replan(
        self,
        reason: str,
        new_plan: Optional[List[Dict[str, str]]] = None,
    ) -> TrajectoryStep:
        """Record a replanning step."""
        detail: Dict[str, Any] = {"reason": reason}
        if new_plan:
            detail["new_plan"] = new_plan
        return self._add_step(
            action_type=ActionType.REPLAN,
            action_detail=detail,
        )

    def record_step(
        self,
        action_type: str,
        action_detail: Dict[str, Any],
        observation: Optional[str] = None,
    ) -> TrajectoryStep:
        """Generic step recording - for custom action_type."""
        return self._add_step(
            action_type=action_type,
            action_detail=action_detail,
            observation=observation,
        )

    # ---- Internal Methods ----

    def _add_step(
        self,
        action_type: str,
        action_detail: Dict[str, Any],
        observation: Optional[str] = None,
    ) -> TrajectoryStep:
        """Create step and send to Collector."""
        if not self._is_active:
            if self._config.auto_start_task:
                self.start_task()
            else:
                raise TaskNotCreatedError(
                    "Tracker is not active. Call start_task() first "
                    "or set auto_start_task=True."
                )

        step = self._collector.add_step(
            action_type=action_type,
            action_detail=action_detail,
            observation=observation,
        )

        # Send to report queue
        self._reporter.enqueue(step)

        return step
