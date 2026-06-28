"""
IncrementalEvalService — re-evaluate only changed dimensions.

When the agent prompt, tools, or retrieval config change, only a subset of
evaluation dimensions are affected.  This service detects what changed by
comparing trajectories and re-runs only the affected evaluators, reusing
cached scores for the rest.

Change-impact mapping:
    - prompt / plan changes  → planning, tactical
    - tool changes           → tool_use
    - retrieval config       → retrieval
    - memory config          → memory, replan
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.config import settings
from app.db.database import async_session_factory
from app.db.models import AgentTask, AgentTrajectory, Evaluation, EvaluationStatus, TaskStatus
from app.graphs.evaluation_graph import evaluate_parallel
from app.models.schemas import TrajectoryDiffResponse, TrajectoryStep
from app.services.diff_service import DiffService

logger = logging.getLogger(__name__)

# Mapping from detected change pattern to affected evaluation dimensions
CHANGE_DIMENSION_MAP: Dict[str, List[str]] = {
    "planning": ["planning", "tactical"],
    "tactical": ["tactical"],
    "tool_use": ["tool_use"],
    "memory": ["memory", "replan"],
    "replan": ["replan"],
    "retrieval": ["retrieval"],
}


class IncrementalEvalService:
    """Run partial evaluation — only changed dimensions."""

    def __init__(self) -> None:
        self.diff_service = DiffService()

    async def incremental_evaluate(
        self,
        base_eval_id: str,
        head_task_id: str,
        force_dims: Optional[List[str]] = None,
        workspace_id: Optional[str] = None,
    ) -> Tuple[str, List[str], List[str], TrajectoryDiffResponse, str, Optional[float]]:
        """
        Run an incremental evaluation.

        Args:
            base_eval_id: Previous evaluation to reuse scores from.
            head_task_id: New task with updated trajectory.
            force_dims: Override — force re-evaluate these dimensions.
            workspace_id: For access control.

        Returns:
            Tuple of (evaluation_id, reused_dims, re_evaluated_dims, diff_summary).
        """
        async with async_session_factory() as db:
            from sqlalchemy.orm import selectinload

            # ── Fetch base evaluation with eager-loaded task ──
            base_eval = await db.get(
                Evaluation,
                base_eval_id,
                options=[selectinload(Evaluation.task)],
            )
            if not base_eval or base_eval.status != EvaluationStatus.COMPLETED:
                raise ValueError(f"Base evaluation {base_eval_id} not found or not completed")

            # ── Fetch head task + trajectory ──
            head_task = await db.get(AgentTask, head_task_id)
            if not head_task:
                raise ValueError(f"Head task {head_task_id} not found")

            head_traj = await self._get_trajectory(db, head_task_id)
            base_traj = await self._get_trajectory(db, base_eval.task_id)

            if not head_traj:
                raise ValueError("Head task has no trajectory")

            # ── Detect changes (generate eval_id first so diff has a real head ID) ──
            import uuid

            eval_id = str(uuid.uuid4())
            diff = await self.diff_service.compare(
                base_trajectory=base_traj,
                head_trajectory=head_traj,
                base_eval_id=base_eval_id,
                head_eval_id=eval_id,
                base_goal=base_eval.task.goal if base_eval.task else "",
                head_goal=head_task.goal,
            )

            # ── Determine which dimensions to re-evaluate ──
            if force_dims:
                re_eval_dims = force_dims
            else:
                re_eval_dims = self._detect_changed_dimensions(diff)

            all_dims = ["planning", "tactical", "tool_use", "memory", "replan", "retrieval"]
            reused_dims = [d for d in all_dims if d not in re_eval_dims]

            # ── Create new evaluation record (reuse eval_id from above) ──
            from datetime import datetime, timezone

            from app.agent_runtime.prompts import PROMPT_VERSION
            from app.core.config import settings as _cfg

            new_eval = Evaluation(
                id=eval_id,
                task_id=head_task_id,
                status=EvaluationStatus.IN_PROGRESS,
                created_at=datetime.now(timezone.utc),
                prompt_version=PROMPT_VERSION,
                model_name=_cfg.DEFAULT_LLM_MODEL,
                model_provider=_cfg.DEFAULT_LLM_PROVIDER,
            )
            db.add(new_eval)
            await db.flush()

            # ── Run full eval on changed dimensions ──
            if re_eval_dims:
                steps = [
                    TrajectoryStep(
                        step_number=s["step_number"],
                        action_type=s["action_type"],
                        action_detail=s.get("action_detail", {}),
                        observation=s.get("observation"),
                    )
                    for s in head_traj
                ]
                full_result = await evaluate_parallel(head_task.goal, steps, head_task.context)

                # Take only the re-evaluated dimensions
                for dim in re_eval_dims:
                    dim_data = full_result.get(dim)
                    if dim_data:
                        setattr(new_eval, f"{dim}_score", dim_data.get("overall"))
                        setattr(new_eval, f"{dim}_feedback", dim_data)
            else:
                full_result = {}

            # ── Reuse scores from base for unchanged dimensions ──
            for dim in reused_dims:
                base_score = getattr(base_eval, f"{dim}_score", None)
                base_feedback = getattr(base_eval, f"{dim}_feedback", None)
                setattr(new_eval, f"{dim}_score", base_score)
                setattr(new_eval, f"{dim}_feedback", base_feedback)

            # ── Compute overall score ──
            all_scores = {}
            for dim in all_dims:
                score = getattr(new_eval, f"{dim}_score", None)
                feedback = getattr(new_eval, f"{dim}_feedback", None)
                all_scores[dim] = {"overall": score, **feedback} if feedback else {"overall": score}

            from app.core.config import settings as _cfg

            weights = _cfg.EVAL_DIMENSION_WEIGHTS
            overall = sum(
                weights.get(d, 0) * (all_scores[d].get("overall", 0) if isinstance(all_scores[d], dict) else 0)
                for d in all_dims
            )
            new_eval.overall_score = round(overall, 1)
            new_eval.status = EvaluationStatus.COMPLETED
            new_eval.completed_at = datetime.now(timezone.utc)

            head_task.status = TaskStatus.COMPLETED
            head_task.completed_at = datetime.now(timezone.utc)

            await db.flush()

            return eval_id, reused_dims, re_eval_dims, diff, new_eval.status.value, new_eval.overall_score

    def _detect_changed_dimensions(self, diff: TrajectoryDiffResponse) -> List[str]:
        """Map trajectory changes to affected evaluation dimensions."""
        if diff.total_changes == 0:
            return []

        changed_dims: Set[str] = set()

        # Check for specific change patterns in the steps
        for step in diff.steps:
            if step.change_type == "unchanged":
                continue

            if not step.after:
                continue

            # Check action_type changes
            action_type = (step.after or {}).get("action_type", "")
            action_detail = (step.after or {}).get("action_detail", {})

            # Plan-related changes
            if action_type in ("plan", "plan_update", "replan"):
                changed_dims.update(CHANGE_DIMENSION_MAP["planning"])
                changed_dims.update(CHANGE_DIMENSION_MAP["replan"])

            # Tool-related changes
            if action_type == "tool_call":
                tool_name = ""
                if isinstance(action_detail, dict):
                    tool_name = action_detail.get("tool", "") or action_detail.get("name", "")
                if tool_name:
                    changed_dims.update(CHANGE_DIMENSION_MAP["tool_use"])

            # Retrieval-related
            if action_type in ("retrieval", "evidence"):
                changed_dims.update(CHANGE_DIMENSION_MAP["retrieval"])

            # Memory-related
            if action_type in ("memory_write", "memory_read"):
                changed_dims.update(CHANGE_DIMENSION_MAP["memory"])

        return list(changed_dims) if changed_dims else ["planning", "tactical"]

    async def _get_trajectory(self, db, task_id: str) -> List[Dict[str, Any]]:
        """Fetch trajectory steps for a task."""
        from sqlalchemy import select

        result = await db.execute(
            select(AgentTrajectory).where(AgentTrajectory.task_id == task_id).order_by(AgentTrajectory.step_number)
        )
        steps = result.scalars().all()
        return [
            {
                "step_number": s.step_number,
                "action_type": s.action_type,
                "action_detail": s.action_detail,
                "observation": s.observation,
                "timestamp": s.timestamp.isoformat() if s.timestamp else None,
            }
            for s in steps
        ]
