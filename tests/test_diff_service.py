"""Tests for DiffService — trajectory comparison."""

from __future__ import annotations

from app.models.schemas import StepDiff, TrajectoryDiffResponse
from app.services.diff_service import DiffService


class TestDiffService:
    """Tests for the trajectory diff service."""

    def setup_method(self):
        self.service = DiffService()

    def _make_step(self, num, action_type="plan", detail=None, observation=None):
        return {
            "step_number": num,
            "action_type": action_type,
            "action_detail": detail or {"plan": f"Step {num}"},
            "observation": observation,
            "timestamp": "2025-01-01T00:00:00Z",
        }

    async def test_identical_trajectories(self):
        """Should return no changes for identical trajectories."""
        steps = [self._make_step(1), self._make_step(2)]
        result = await self.service.compare(steps, steps, "base-1", "head-1")

        assert isinstance(result, TrajectoryDiffResponse)
        assert result.total_changes == 0
        assert result.steps_added == 0
        assert result.steps_removed == 0
        assert result.steps_modified == 0
        assert len(result.steps) == 2
        for s in result.steps:
            assert s.change_type == "unchanged"

    async def test_added_step(self):
        """Should detect added steps."""
        base = [self._make_step(1), self._make_step(2)]
        head = [self._make_step(1), self._make_step(2), self._make_step(3)]

        result = await self.service.compare(base, head, "base-1", "head-1")

        assert result.total_changes == 1
        assert result.steps_added == 1
        added = [s for s in result.steps if s.change_type == "added"]
        assert len(added) == 1
        assert added[0].step_number == 3

    async def test_removed_step(self):
        """Should detect removed steps."""
        base = [self._make_step(1), self._make_step(2), self._make_step(3)]
        head = [self._make_step(1), self._make_step(3)]

        result = await self.service.compare(base, head, "base-1", "head-1")

        assert result.total_changes == 1
        assert result.steps_removed == 1
        removed = [s for s in result.steps if s.change_type == "removed"]
        assert len(removed) == 1
        assert removed[0].step_number == 2

    async def test_modified_step(self):
        """Should detect modified steps (action_type or detail change)."""
        base = [self._make_step(1, action_type="plan", detail={"plan": "Do X"})]
        head = [self._make_step(1, action_type="tool_call", detail={"tool": "python", "code": "print(1)"})]

        result = await self.service.compare(base, head, "base-1", "head-1")

        assert result.total_changes == 1
        assert result.steps_modified == 1
        changed = [s for s in result.steps if s.change_type == "changed"]
        assert len(changed) == 1
        assert "action_type" in changed[0].field_changes
        assert "action_detail.plan" in changed[0].field_changes or "action_detail.tool" in changed[0].field_changes

    async def test_excludes_llm_trace_from_diff(self):
        """Should not report _llm_trace metadata as a change."""
        base = [self._make_step(1)]
        head = [
            {
                "step_number": 1,
                "action_type": "plan",
                "action_detail": {"plan": "Step 1", "_llm_trace": {"prompt": "...", "response": "..."}},
                "observation": None,
            }
        ]

        result = await self.service.compare(base, head, "base-1", "head-1")

        # The plans are the same, but base doesn't have _llm_trace
        # The _clean_detail removes _llm_trace before comparison
        unchanged = [s for s in result.steps if s.change_type == "unchanged"]
        assert len(unchanged) == 1

    async def test_observation_change(self):
        """Should detect observation changes."""
        base = [self._make_step(1, observation="old output")]
        head = [self._make_step(1, observation="new output")]

        result = await self.service.compare(base, head, "base-1", "head-1")

        changed = [s for s in result.steps if s.change_type == "changed"]
        assert len(changed) == 1
        assert "observation" in changed[0].field_changes

    async def test_empty_trajectories(self):
        """Should handle empty trajectory lists."""
        result = await self.service.compare([], [], "base-1", "head-1")

        assert result.total_changes == 0
        assert len(result.steps) == 0

    async def test_metadata_set_on_response(self):
        """Should set metadata fields correctly."""
        base = [self._make_step(1)]
        head = [self._make_step(1), self._make_step(2)]

        result = await self.service.compare(
            base,
            head,
            base_eval_id="base-eval-1",
            head_eval_id="head-eval-1",
            base_goal="Goal A",
            head_goal="Goal B",
        )

        assert result.base_evaluation_id == "base-eval-1"
        assert result.head_evaluation_id == "head-eval-1"
        assert result.base_task_goal == "Goal A"
        assert result.head_task_goal == "Goal B"
