"""Tests for Golden Test Suite — validates each case structure and runner logic."""

from __future__ import annotations

import pytest

from app.benchmarks.golden import GOLDEN_SUITE, GoldenCase
from app.benchmarks.golden.runner import GoldenResult, GoldenSuiteRunner


class TestGoldenSuiteData:
    """Structural validation of golden case definitions."""

    def test_suite_is_not_empty(self):
        """Should have at least one golden case."""
        assert len(GOLDEN_SUITE) > 0

    def test_all_cases_have_required_fields(self):
        """Each case must have id, description, goal, trajectory, expected_ranges."""
        for case in GOLDEN_SUITE:
            assert isinstance(case, GoldenCase)
            assert case.id, f"Case missing id: {case}"
            assert case.description, f"Case {case.id} missing description"
            assert case.goal, f"Case {case.id} missing goal"
            assert len(case.trajectory) > 0, f"Case {case.id} has empty trajectory"
            assert len(case.expected_ranges) > 0, f"Case {case.id} has no expected_ranges"

    def test_all_case_ids_unique(self):
        """Each case must have a unique ID."""
        ids = [c.id for c in GOLDEN_SUITE]
        assert len(ids) == len(set(ids)), f"Duplicate case IDs: {ids}"

    def test_each_step_has_required_keys(self):
        """Each trajectory step must have step_number, action_type, action_detail."""
        for case in GOLDEN_SUITE:
            for i, step in enumerate(case.trajectory):
                assert "step_number" in step, f"{case.id} step {i} missing step_number"
                assert "action_type" in step, f"{case.id} step {i} missing action_type"
                assert "action_detail" in step, f"{case.id} step {i} missing action_detail"

    def test_expected_ranges_valid(self):
        """Each expected range must be (min, max) with min <= max."""
        for case in GOLDEN_SUITE:
            for dim, (min_s, max_s) in case.expected_ranges.items():
                assert min_s <= max_s, f"{case.id} {dim}: min {min_s} > max {max_s}"
                assert 0 <= min_s <= 100, f"{case.id} {dim}: min {min_s} out of range"
                assert 0 <= max_s <= 100, f"{case.id} {dim}: max {max_s} out of range"

    def test_each_case_covers_planning_and_tool_use(self):
        """Each case should at minimum specify planning and tool_use ranges."""
        for case in GOLDEN_SUITE:
            assert "planning" in case.expected_ranges, f"{case.id} missing planning range"
            assert "tool_use" in case.expected_ranges, f"{case.id} missing tool_use range"

    def test_trajectory_step_numbers_monotonic(self):
        """Step numbers must be monotonically increasing (allow gaps for legacy compat)."""
        for case in GOLDEN_SUITE:
            nums = [s["step_number"] for s in case.trajectory]
            for i in range(1, len(nums)):
                assert nums[i] > nums[i - 1], f"{case.id}: step {nums[i]} <= previous {nums[i - 1]}"


class TestGoldenRunner:
    """Tests for GoldenSuiteRunner logic (without calling evaluators)."""

    def setup_method(self):
        self.runner = GoldenSuiteRunner()

    @pytest.mark.asyncio
    async def test_run_single_returns_result(self):
        """_run_single should return a GoldenResult."""
        # Use a minimal case
        case = GOLDEN_SUITE[0]
        result = await self.runner._run_single(case)

        assert isinstance(result, GoldenResult)
        assert result.case_id == case.id

    def test_golden_result_dataclass(self):
        """GoldenResult should correctly report pass/fail."""
        result = GoldenResult(
            case_id="test",
            description="test",
            passed=True,
            scores={"planning": 85.0, "tactical": 90.0},
            failures=[],
            duration_ms=100.0,
        )
        assert result.passed is True
        assert len(result.failures) == 0
        assert result.scores["planning"] == 85.0
