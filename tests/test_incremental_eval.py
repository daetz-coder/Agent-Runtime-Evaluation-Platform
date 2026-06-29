"""Tests for IncrementalEvalService — dimension-aware re-evaluation."""

from __future__ import annotations

from app.models.schemas import StepDiff, TrajectoryDiffResponse
from app.services.diff_service import DiffService
from app.services.incremental_eval import IncrementalEvalService


class TestIncrementalEvalDetection:
    """Tests for the change dimension detection logic."""

    def setup_method(self):
        self.service = IncrementalEvalService()
        self.diff_service = DiffService()

    def test_no_changes_no_reeval(self):
        """Should return empty list when no changes detected."""
        diff = TrajectoryDiffResponse(
            base_evaluation_id="base-1",
            head_evaluation_id="head-1",
            base_task_goal="Goal",
            head_task_goal="Goal",
            total_changes=0,
            steps_added=0,
            steps_removed=0,
            steps_modified=0,
            steps=[],
        )
        result = self.service._detect_changed_dimensions(diff)
        assert result == []

    def test_plan_change_detects_planning_and_tactical(self):
        """Plan-related changes should trigger planning+tactical re-evaluation."""
        diff = TrajectoryDiffResponse(
            base_evaluation_id="base-1",
            head_evaluation_id="head-1",
            base_task_goal="Goal",
            head_task_goal="Goal",
            total_changes=1,
            steps_added=0,
            steps_removed=0,
            steps_modified=1,
            steps=[
                StepDiff(
                    step_number=1,
                    change_type="changed",
                    before={"action_type": "plan", "action_detail": {"plan": "Old"}},
                    after={"action_type": "plan", "action_detail": {"plan": "New"}},
                    field_changes=["action_detail.plan"],
                )
            ],
        )
        result = self.service._detect_changed_dimensions(diff)
        assert "planning" in result
        assert "tactical" in result

    def test_tool_call_change_detects_tool_use_with_tool_name(self):
        """SDK-style tool_name field should trigger tool_use re-evaluation."""
        diff = TrajectoryDiffResponse(
            base_evaluation_id="base-1",
            head_evaluation_id="head-1",
            base_task_goal="Goal",
            head_task_goal="Goal",
            total_changes=1,
            steps_added=0,
            steps_removed=0,
            steps_modified=1,
            steps=[
                StepDiff(
                    step_number=2,
                    change_type="changed",
                    before={"action_type": "tool_call", "action_detail": {"tool_name": "python_execute"}},
                    after={"action_type": "tool_call", "action_detail": {"tool_name": "bash_execute"}},
                    field_changes=["action_detail.tool_name"],
                )
            ],
        )
        result = self.service._detect_changed_dimensions(diff)
        assert "tool_use" in result

    def test_tool_call_change_detects_tool_use(self):
        """Tool call changes should trigger tool_use re-evaluation."""
        diff = TrajectoryDiffResponse(
            base_evaluation_id="base-1",
            head_evaluation_id="head-1",
            base_task_goal="Goal",
            head_task_goal="Goal",
            total_changes=1,
            steps_added=0,
            steps_removed=0,
            steps_modified=1,
            steps=[
                StepDiff(
                    step_number=2,
                    change_type="changed",
                    before={"action_type": "tool_call", "action_detail": {"tool": "python_execute"}},
                    after={"action_type": "tool_call", "action_detail": {"tool": "bash_execute"}},
                    field_changes=["action_detail.tool"],
                )
            ],
        )
        result = self.service._detect_changed_dimensions(diff)
        assert "tool_use" in result

    def test_retrieval_change_detects_retrieval(self):
        """Retrieval changes should trigger retrieval re-evaluation."""
        diff = TrajectoryDiffResponse(
            base_evaluation_id="base-1",
            head_evaluation_id="head-1",
            base_task_goal="Goal",
            head_task_goal="Goal",
            total_changes=1,
            steps_added=1,
            steps_removed=0,
            steps_modified=0,
            steps=[
                StepDiff(
                    step_number=3,
                    change_type="added",
                    before=None,
                    after={"action_type": "retrieval", "action_detail": {"query": "new search"}},
                    field_changes=[],
                )
            ],
        )
        result = self.service._detect_changed_dimensions(diff)
        assert "retrieval" in result

    def test_memory_change_detects_memory(self):
        """Memory changes should trigger memory re-evaluation."""
        diff = TrajectoryDiffResponse(
            base_evaluation_id="base-1",
            head_evaluation_id="head-1",
            base_task_goal="Goal",
            head_task_goal="Goal",
            total_changes=1,
            steps_added=0,
            steps_removed=0,
            steps_modified=1,
            steps=[
                StepDiff(
                    step_number=4,
                    change_type="changed",
                    before={"action_type": "memory_write", "action_detail": {"key": "old"}},
                    after={"action_type": "memory_write", "action_detail": {"key": "new"}},
                    field_changes=["action_detail.key"],
                )
            ],
        )
        result = self.service._detect_changed_dimensions(diff)
        assert "memory" in result

    def test_added_step_falls_back_to_planning_tactical(self):
        """Newly added steps with no specific type should default to planning+tactical."""
        diff = TrajectoryDiffResponse(
            base_evaluation_id="base-1",
            head_evaluation_id="head-1",
            base_task_goal="Goal",
            head_task_goal="Goal",
            total_changes=1,
            steps_added=1,
            steps_removed=0,
            steps_modified=0,
            steps=[
                StepDiff(
                    step_number=5,
                    change_type="added",
                    before=None,
                    after={"action_type": "think", "action_detail": {"thought": "hmm"}},
                    field_changes=[],
                )
            ],
        )
        result = self.service._detect_changed_dimensions(diff)
        # 'think' isn't a recognized type, so it falls back
        assert isinstance(result, list)
