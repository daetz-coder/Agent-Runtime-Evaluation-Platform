"""
Base evaluator class for all evaluation dimensions.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

from app.core.config import settings
from app.models.schemas import TrajectoryStep


class BaseEvaluator(ABC):
    """Base class for all evaluators."""

    def __init__(self, llm: Optional[BaseChatModel] = None):
        """Initialize evaluator with optional LLM override."""
        self.llm = llm or self._get_default_llm()

    def _get_default_llm(self) -> BaseChatModel:
        """Get default LLM based on configuration."""
        provider = settings.DEFAULT_LLM_PROVIDER.lower()

        if provider == "anthropic":
            return ChatAnthropic(
                model=settings.DEFAULT_LLM_MODEL,
                anthropic_api_key=settings.ANTHROPIC_API_KEY,
                temperature=0,
            )
        elif provider == "deepseek":
            # DeepSeek API is compatible with OpenAI API format
            return ChatOpenAI(
                model=settings.DEEPSEEK_MODEL,
                openai_api_key=settings.DEEPSEEK_API_KEY,
                openai_api_base=settings.DEEPSEEK_BASE_URL,
                temperature=0,
            )
        else:  # openai
            return ChatOpenAI(
                model=settings.DEFAULT_LLM_MODEL,
                openai_api_key=settings.OPENAI_API_KEY,
                temperature=0,
            )

    @abstractmethod
    async def evaluate(
        self,
        goal: str,
        trajectory: List[TrajectoryStep],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate agent behavior.

        Args:
            goal: The original goal/objective
            trajectory: List of agent execution steps
            context: Additional context for evaluation

        Returns:
            Dictionary containing scores and feedback
        """
        pass

    def _format_trajectory(self, trajectory: List[TrajectoryStep]) -> str:
        """Format trajectory steps into readable text."""
        lines = []
        for step in trajectory:
            lines.append(f"Step {step.step_number} [{step.action_type}]:")
            lines.append(f"  Action: {step.action_detail}")
            if step.observation:
                lines.append(f"  Observation: {step.observation}")
            lines.append("")
        return "\n".join(lines)

    def _extract_plans(self, trajectory: List[TrajectoryStep]) -> List[Dict[str, Any]]:
        """Extract planning steps from trajectory."""
        return [
            step.action_detail
            for step in trajectory
            if step.action_type == "plan"
        ]

    def _extract_tool_calls(self, trajectory: List[TrajectoryStep]) -> List[Dict[str, Any]]:
        """Extract tool call steps from trajectory."""
        return [
            {
                "step": step.step_number,
                "tool": step.action_detail.get("tool_name"),
                "input": step.action_detail.get("input"),
                "output": step.observation,
            }
            for step in trajectory
            if step.action_type == "tool_call"
        ]

    def _extract_replans(self, trajectory: List[TrajectoryStep]) -> List[Dict[str, Any]]:
        """Extract replanning events from trajectory."""
        return [
            {
                "step": step.step_number,
                "reason": step.action_detail.get("reason"),
                "new_plan": step.action_detail.get("new_plan"),
            }
            for step in trajectory
            if step.action_type == "replan"
        ]

    def _calculate_weighted_score(self, scores: Dict[str, float], weights: Dict[str, float]) -> float:
        """Calculate weighted average score."""
        total_weight = sum(weights.values())
        weighted_sum = sum(scores.get(k, 0) * v for k, v in weights.items())
        return weighted_sum / total_weight if total_weight > 0 else 0
