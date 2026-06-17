"""
Base agent class for example agents.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from app.models.schemas import TrajectoryStep


class BaseAgent(ABC):
    """
    Base class for example agents.

    This is used for demonstration and testing purposes.
    The evaluation platform evaluates external agent trajectories,
    not these agents directly.
    """

    def __init__(
        self,
        llm: BaseChatModel,
        tools: Optional[List[BaseTool]] = None,
    ):
        self.llm = llm
        self.tools = tools or []
        self.trajectory: List[TrajectoryStep] = []
        self.step_counter = 0

    @abstractmethod
    async def run(self, goal: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Run the agent to achieve a goal.

        Args:
            goal: The goal/objective to achieve
            context: Additional context

        Returns:
            Dictionary with result and metadata
        """
        pass

    def _record_step(
        self,
        action_type: str,
        action_detail: Dict[str, Any],
        observation: Optional[str] = None,
    ) -> None:
        """Record a trajectory step."""
        self.step_counter += 1
        step = TrajectoryStep(
            step_number=self.step_counter,
            action_type=action_type,
            action_detail=action_detail,
            observation=observation,
            timestamp=datetime.utcnow(),
        )
        self.trajectory.append(step)

    def _record_plan(self, plan: Dict[str, Any]) -> None:
        """Record a planning step."""
        self._record_step(
            action_type="plan",
            action_detail=plan,
        )

    def _record_tool_call(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_output: Optional[str] = None,
    ) -> None:
        """Record a tool call step."""
        self._record_step(
            action_type="tool_call",
            action_detail={
                "tool_name": tool_name,
                "input": tool_input,
            },
            observation=tool_output,
        )

    def _record_think(self, thought: str) -> None:
        """Record a thinking step."""
        self._record_step(
            action_type="think",
            action_detail={"thought": thought},
        )

    def _record_replan(self, reason: str, new_plan: Dict[str, Any]) -> None:
        """Record a replanning step."""
        self._record_step(
            action_type="replan",
            action_detail={
                "reason": reason,
                "new_plan": new_plan,
            },
        )

    def get_trajectory(self) -> List[Dict[str, Any]]:
        """Get trajectory as list of dictionaries."""
        return [step.model_dump() for step in self.trajectory]

    def reset(self) -> None:
        """Reset agent state."""
        self.trajectory = []
        self.step_counter = 0
