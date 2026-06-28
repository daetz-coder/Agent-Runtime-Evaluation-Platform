"""Tests for one-click legacy evaluation endpoint."""

from __future__ import annotations

from datetime import datetime, timezone

from app.models.schemas import TrajectoryStep


class TestRunLegacySchema:
    """Test schemas used by the run-legacy endpoint."""

    def test_trajectory_step_validation(self):
        """TrajectoryStep should accept required fields."""
        step = TrajectoryStep(
            step_number=1,
            action_type="plan",
            action_detail={"plan": "test"},
        )
        assert step.step_number == 1
        assert step.action_type == "plan"

    def test_trajectory_step_with_observation(self):
        """Should accept optional observation."""
        step = TrajectoryStep(
            step_number=2,
            action_type="tool_call",
            action_detail={"tool": "python", "code": "print(1)"},
            observation="1",
        )
        assert step.observation == "1"
