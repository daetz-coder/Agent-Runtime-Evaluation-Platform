"""
ReplayService — step-by-step replay debug data for agent trajectories.

Extracts LLM trace information from each trajectory step's action_detail
and assembles a chronological replay view for debugging agent behavior.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from app.db.models import Evaluation
from app.models.schemas import LLMTraceInfo, ReplayResponse

logger = logging.getLogger(__name__)


class ReplayService:
    """Build replay debug data from a completed evaluation."""

    async def get_replay(
        self,
        evaluation: Evaluation,
        trajectory: List[dict],
        goal: str,
    ) -> ReplayResponse:
        """
        Assemble step-by-step replay data for an evaluation.

        Args:
            evaluation: The Evaluation ORM instance.
            trajectory: Raw trajectory steps (list of dicts from DB).
            goal: The agent's goal/task.

        Returns:
            ReplayResponse with per-step LLM trace info.
        """
        steps: List[LLMTraceInfo] = []

        for step in trajectory:
            action_detail = step.get("action_detail") or {}
            llm_trace = action_detail.get("_llm_trace", {})

            steps.append(
                LLMTraceInfo(
                    step_number=step.get("step_number", 0),
                    action_type=step.get("action_type", "unknown"),
                    llm_prompt=llm_trace.get("prompt", ""),
                    llm_response=llm_trace.get("response", ""),
                    llm_model=llm_trace.get("model", "unknown"),
                    latency_ms=float(llm_trace.get("latency_ms", 0)),
                )
            )

        return ReplayResponse(
            task_id=evaluation.task_id,
            evaluation_id=evaluation.id,
            goal=goal,
            step_count=len(steps),
            steps=steps,
        )

    @staticmethod
    def inject_llm_trace(
        action_detail: dict,
        *,
        prompt: str,
        response: str,
        model: str = "unknown",
        latency_ms: float = 0,
    ) -> dict:
        """
        Inject LLM trace data into an action_detail dict.

        Agent runtime should call this before recording each trajectory step
        so the replay debugger has full visibility.

        Returns the modified action_detail (mutated in-place for convenience).
        """
        action_detail["_llm_trace"] = {
            "prompt": prompt[:10000],
            "response": response[:10000],
            "model": model,
            "latency_ms": latency_ms,
        }
        return action_detail
