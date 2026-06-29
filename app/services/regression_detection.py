"""
RegressionDetectionService — detect score regressions across evaluations.

Compares a new evaluation against a baseline (e.g. main branch) and flags
dimensions where the score dropped beyond a configurable threshold.

Integrates with the DiffService to explain *why* a regression occurred.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from app.db.database import async_session_factory
from app.db.models import Evaluation
from app.models.schemas import TrajectoryDiffResponse

logger = logging.getLogger(__name__)

# Default thresholds per dimension (drop in score that triggers an alert)
DEFAULT_THRESHOLDS: Dict[str, float] = {
    "overall": -5.0,
    "planning": -10.0,
    "tactical": -10.0,
    "tool_use": -8.0,
    "memory": -10.0,
    "replan": -10.0,
    "retrieval": -10.0,
}

ALL_DIMS = ["planning", "tactical", "tool_use", "memory", "replan", "retrieval"]


@dataclass
class RegressionReport:
    """Report of detected regressions."""

    base_evaluation_id: str
    head_evaluation_id: str
    has_regression: bool = False
    dimensions: Dict[str, "DimensionChange"] = field(default_factory=dict)
    overall_change: float = 0.0
    summary: str = ""
    diff: Optional[TrajectoryDiffResponse] = None


@dataclass
class DimensionChange:
    """Score change for a single dimension."""

    dimension: str
    base_score: float
    head_score: float
    delta: float
    is_regression: bool
    threshold: float


class RegressionDetectionService:
    """Detect score regressions by comparing evaluations."""

    def __init__(self, thresholds: Optional[Dict[str, float]] = None):
        self.thresholds = thresholds or DEFAULT_THRESHOLDS

    async def compare(
        self,
        base_eval_id: str,
        head_eval_id: str,
        include_diff: bool = True,
        workspace_id: Optional[str] = None,
    ) -> RegressionReport:
        """
        Compare two evaluations by ID and detect regressions.

        Args:
            base_eval_id: Reference (baseline) evaluation ID.
            head_eval_id: New evaluation ID to check.
            include_diff: If True, include trajectory diff in the report.
            workspace_id: If set, verify both evaluations belong to this workspace.

        Returns:
            RegressionReport with per-dimension deltas and regression flags.
        """
        async with async_session_factory() as db:
            from app.db.models import AgentTask

            base_eval = await db.get(Evaluation, base_eval_id)
            head_eval = await db.get(Evaluation, head_eval_id)

            if not base_eval or not head_eval:
                raise ValueError("One or both evaluations not found")

            if workspace_id:
                base_task = await db.get(AgentTask, base_eval.task_id)
                head_task = await db.get(AgentTask, head_eval.task_id)
                if not base_task or base_task.workspace_id != workspace_id:
                    raise ValueError("Base evaluation not found in this workspace")
                if not head_task or head_task.workspace_id != workspace_id:
                    raise ValueError("Head evaluation not found in this workspace")

            report = self._compare_objects(
                base_eval=base_eval,
                head_eval=head_eval,
                base_eval_id=base_eval_id,
                head_eval_id=head_eval_id,
            )

            # Optionally include trajectory diff (needs DB access)
            if include_diff:
                try:
                    from sqlalchemy import select

                    from app.db.models import AgentTask, AgentTrajectory
                    from app.services.diff_service import DiffService

                    async def _get_traj(task_id: str) -> list:
                        r = await db.execute(
                            select(AgentTrajectory)
                            .where(AgentTrajectory.task_id == task_id)
                            .order_by(AgentTrajectory.step_number)
                        )
                        return [
                            {
                                "step_number": s.step_number,
                                "action_type": s.action_type,
                                "action_detail": s.action_detail,
                                "observation": s.observation,
                            }
                            for s in r.scalars().all()
                        ]

                    base_traj = await _get_traj(base_eval.task_id)
                    head_traj = await _get_traj(head_eval.task_id)

                    base_task = await db.get(AgentTask, base_eval.task_id)
                    head_task = await db.get(AgentTask, head_eval.task_id)

                    diff_service = DiffService()
                    report.diff = await diff_service.compare(
                        base_trajectory=base_traj,
                        head_trajectory=head_traj,
                        base_eval_id=base_eval_id,
                        head_eval_id=head_eval_id,
                        base_goal=base_task.goal if base_task else "",
                        head_goal=head_task.goal if head_task else "",
                    )
                except (LookupError, OSError, ValueError, RuntimeError) as e:
                    logger.warning("Failed to compute diff for regression report: %s", e)

            return report

    def _compare_objects(
        self,
        base_eval: Any,
        head_eval: Any,
        base_eval_id: str = "",
        head_eval_id: str = "",
    ) -> RegressionReport:
        """
        Compare two evaluation objects directly (no DB lookup).

        Extracted for testability — accepts any object with
        ``overall_score`` and ``{dim}_score`` attributes.
        """
        dims: Dict[str, DimensionChange] = {}

        for dim in ALL_DIMS:
            base_score = float(getattr(base_eval, f"{dim}_score", None) or 0)
            head_score = float(getattr(head_eval, f"{dim}_score", None) or 0)
            delta = head_score - base_score
            threshold = self.thresholds.get(dim, -10.0)
            is_reg = delta < threshold

            dims[dim] = DimensionChange(
                dimension=dim,
                base_score=base_score,
                head_score=head_score,
                delta=round(delta, 1),
                is_regression=is_reg,
                threshold=threshold,
            )

        overall_base = float(base_eval.overall_score or 0)
        overall_head = float(head_eval.overall_score or 0)
        overall_delta = round(overall_head - overall_base, 1)
        overall_threshold = self.thresholds.get("overall", -5.0)
        has_regression = overall_delta < overall_threshold or any(d.is_regression for d in dims.values())

        # Build human-readable summary
        regressed_dims = [d for d in dims.values() if d.is_regression]
        if regressed_dims:
            dim_summaries = [f"{d.dimension}: {d.base_score}→{d.head_score} ({d.delta})" for d in regressed_dims]
            summary = (
                f"Regression detected! Overall: {overall_base}→{overall_head} ({overall_delta}). "
                f"Regressed dimensions: {', '.join(dim_summaries)}"
            )
        elif has_regression:
            summary = (
                f"Regression detected! Overall: {overall_base}→{overall_head} ({overall_delta}). "
                f"(No individual dimension exceeded its threshold, but overall did.)"
            )
        else:
            summary = f"No regression. Overall: {overall_base}→{overall_head} ({overall_delta})."

        return RegressionReport(
            base_evaluation_id=base_eval_id,
            head_evaluation_id=head_eval_id,
            has_regression=has_regression,
            dimensions=dims,
            overall_change=overall_delta,
            summary=summary,
        )
