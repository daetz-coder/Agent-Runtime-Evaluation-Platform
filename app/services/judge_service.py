"""
JudgeService — extract raw judge LLM prompt/response for evaluation transparency.

Allows Agent engineers to inspect exactly what prompt was sent to the judge
LLM and what raw response came back, making scores explainable.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

from app.db.models import Evaluation
from app.models.schemas import DIMENSION_NAMES, JudgeRawData

logger = logging.getLogger(__name__)


class JudgeService:
    """Extract raw judge data from evaluation feedback."""

    DIMENSION_FEEDBACK_MAP = {
        "planning": "planning_feedback",
        "tactical": "tactical_feedback",
        "tool_use": "tool_use_feedback",
        "memory": "memory_feedback",
        "replan": "replan_feedback",
        "retrieval": "retrieval_feedback",
    }

    async def get_judge_raw(
        self,
        evaluation: Evaluation,
        dimension: Optional[str] = None,
    ) -> Dict[str, JudgeRawData]:
        """
        Extract raw judge prompt/response for one or all dimensions.

        Args:
            evaluation: Evaluation ORM instance with feedback JSON columns.
            dimension: Optional dimension name (e.g. "planning").
                       None returns all dimensions that have judge raw data.

        Returns:
            Dict mapping dimension name -> JudgeRawData.
        """
        result: Dict[str, JudgeRawData] = {}
        dims = [dimension] if dimension else DIMENSION_NAMES

        for dim in dims:
            feedback_col = self.DIMENSION_FEEDBACK_MAP.get(dim)
            if not feedback_col:
                continue

            feedback_data: dict = getattr(evaluation, feedback_col, None) or {}
            judge_raw: Optional[list] = feedback_data.get("_judge_raw")

            if not judge_raw or not isinstance(judge_raw, list):
                # No raw data for this dimension
                continue

            # Take the LAST judge call for this dimension (the final score)
            last_call = judge_raw[-1] if judge_raw else {}

            # Extract score breakdown from the feedback itself (sub-dimensions)
            score_breakdown = {}
            for key, value in feedback_data.items():
                if key != "_judge_raw" and isinstance(value, (int, float)):
                    score_breakdown[key] = float(value)

            result[dim] = JudgeRawData(
                dimension=dim,
                judge_prompt=last_call.get("prompt", ""),
                judge_response=last_call.get("response", ""),
                judge_model=last_call.get("model", "unknown"),
                score=feedback_data.get("overall"),
                score_breakdown=score_breakdown,
            )

        return result
