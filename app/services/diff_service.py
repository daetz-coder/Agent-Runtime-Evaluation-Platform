"""
DiffService — compare two trajectories and produce a step-by-step diff.

Helps Agent engineers understand exactly what changed between two evaluation
runs, enabling targeted debugging and incremental evaluation.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.models.schemas import StepDiff, TrajectoryDiffResponse

logger = logging.getLogger(__name__)

# Keys to exclude when comparing step details (metadata, not behavior)
_EXCLUDED_KEYS = {"timestamp", "_llm_trace"}


class DiffService:
    """Compare two trajectories and produce structured diffs."""

    async def compare(
        self,
        base_trajectory: List[Dict[str, Any]],
        head_trajectory: List[Dict[str, Any]],
        base_eval_id: str,
        head_eval_id: str,
        base_goal: str = "",
        head_goal: str = "",
    ) -> TrajectoryDiffResponse:
        """
        Produce a step-by-step diff between two trajectories.

        Args:
            base_trajectory: The reference trajectory (e.g. from main branch).
            head_trajectory: The new trajectory to compare.
            base_eval_id: Evaluation ID for the base.
            head_eval_id: Evaluation ID for the head.
            base_goal: Task goal for the base.
            head_goal: Task goal for the head.

        Returns:
            TrajectoryDiffResponse with per-step diffs.
        """
        steps: List[StepDiff] = []
        steps_added = 0
        steps_removed = 0
        steps_modified = 0

        # Index steps by step_number for comparison (group by number to handle duplicates)
        from collections import defaultdict

        base_by_number: Dict[int, List[dict]] = defaultdict(list)
        head_by_number: Dict[int, List[dict]] = defaultdict(list)
        for s in base_trajectory:
            base_by_number[s.get("step_number", 0)].append(s)
        for s in head_trajectory:
            head_by_number[s.get("step_number", 0)].append(s)

        all_numbers = sorted(set(base_by_number.keys()) | set(head_by_number.keys()))

        for step_num in all_numbers:
            base_steps = base_by_number.get(step_num, [])
            head_steps = head_by_number.get(step_num, [])

            # Use first step in each group for comparison
            base_step = base_steps[0] if base_steps else None
            head_step = head_steps[0] if head_steps else None

            if base_step and not head_step:
                # Removed
                steps_removed += 1
                steps.append(
                    StepDiff(
                        step_number=step_num,
                        change_type="removed",
                        before=self._clean_detail(base_step),
                        after=None,
                        field_changes=[],
                    )
                )
            elif head_step and not base_step:
                # Added
                steps_added += 1
                steps.append(
                    StepDiff(
                        step_number=step_num,
                        change_type="added",
                        before=None,
                        after=self._clean_detail(head_step),
                        field_changes=[],
                    )
                )
            else:
                # Both exist — check for changes
                changes = self._compute_changes(base_step, head_step)
                if changes:
                    steps_modified += 1
                    steps.append(
                        StepDiff(
                            step_number=step_num,
                            change_type="changed",
                            before=self._clean_detail(base_step),
                            after=self._clean_detail(head_step),
                            field_changes=changes,
                        )
                    )
                else:
                    steps.append(
                        StepDiff(
                            step_number=step_num,
                            change_type="unchanged",
                            before=None,
                            after=None,
                            field_changes=[],
                        )
                    )

        return TrajectoryDiffResponse(
            base_evaluation_id=base_eval_id,
            head_evaluation_id=head_eval_id,
            base_task_goal=base_goal,
            head_task_goal=head_goal,
            total_changes=steps_added + steps_removed + steps_modified,
            steps_added=steps_added,
            steps_removed=steps_removed,
            steps_modified=steps_modified,
            steps=steps,
        )

    def _compute_changes(self, base: dict, head: dict) -> List[str]:
        """Return list of field names that differ between two steps."""
        changes: List[str] = []

        for key in ("action_type", "observation"):
            if base.get(key) != head.get(key):
                changes.append(key)

        # Compare action_detail fields (excluding metadata)
        base_detail = self._clean_detail_field(base.get("action_detail", {}))
        head_detail = self._clean_detail_field(head.get("action_detail", {}))
        all_keys = set(base_detail.keys()) | set(head_detail.keys())
        for k in all_keys:
            if base_detail.get(k) != head_detail.get(k):
                changes.append(f"action_detail.{k}")

        return changes

    @staticmethod
    def _clean_detail(step: dict) -> Dict[str, Any]:
        """Return a cleaned copy of the step, excluding metadata keys."""
        detail = dict(step.get("action_detail", {}))
        for key in _EXCLUDED_KEYS:
            detail.pop(key, None)
        return {
            "action_type": step.get("action_type"),
            "action_detail": detail,
            "observation": step.get("observation"),
        }

    @staticmethod
    def _clean_detail_field(detail: dict) -> dict:
        """Return action_detail with metadata keys removed."""
        return {k: v for k, v in detail.items() if k not in _EXCLUDED_KEYS}
