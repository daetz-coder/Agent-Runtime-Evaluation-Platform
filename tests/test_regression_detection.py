"""Tests for RegressionDetectionService — score regression checking."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.services.regression_detection import (
    DEFAULT_THRESHOLDS,
    DimensionChange,
    RegressionDetectionService,
    RegressionReport,
)


class TestRegressionDetection:
    """Tests for regression detection service (without DB)."""

    def setup_method(self):
        self.service = RegressionDetectionService()

    def _make_mock_eval(self, dim_scores: dict, overall: float = 80.0):
        """Create a mock Evaluation ORM with given scores."""
        mock = MagicMock()
        mock.id = "eval-xyz"
        mock.task_id = "task-xyz"
        mock.overall_score = overall

        for dim, score in dim_scores.items():
            setattr(mock, f"{dim}_score", score)
        return mock

    def test_no_regression_when_scores_improve(self):
        """Should report no regression when scores improve."""
        base = self._make_mock_eval(
            {"planning": 70.0, "tactical": 70.0, "tool_use": 70.0},
            overall=70.0,
        )
        head = self._make_mock_eval(
            {"planning": 85.0, "tactical": 80.0, "tool_use": 75.0},
            overall=80.0,
        )

        report = self.service.compare(base, head, include_diff=False)

        assert isinstance(report, RegressionReport)
        assert report.has_regression is False
        assert report.overall_change == 10.0
        assert "No regression" in report.summary

    def test_detects_overall_regression(self):
        """Should detect overall score regression below threshold."""
        base = self._make_mock_eval(
            {"planning": 80.0, "tactical": 80.0, "tool_use": 80.0},
            overall=80.0,
        )
        head = self._make_mock_eval(
            {"planning": 75.0, "tactical": 75.0, "tool_use": 75.0},
            overall=60.0,  # -20, threshold is -5
        )

        report = self.service.compare(base, head, include_diff=False)

        assert report.has_regression is True
        assert report.overall_change == -20.0
        assert "Regression detected" in report.summary

    def test_detects_dimension_regression(self):
        """Should detect per-dimension regression even if overall is stable."""
        base = self._make_mock_eval(
            {"planning": 90.0, "tactical": 70.0, "tool_use": 80.0},
            overall=80.0,
        )
        head = self._make_mock_eval(
            {"planning": 75.0, "tactical": 70.0, "tool_use": 80.0},
            overall=75.0,
        )

        report = self.service.compare(base, head, include_diff=False)

        assert report.has_regression is True
        # planning dropped by 15, threshold is -10
        assert report.dimensions["planning"].is_regression is True
        assert report.dimensions["planning"].delta == -15.0
        assert report.dimensions["tactical"].is_regression is False
        assert report.dimensions["tool_use"].is_regression is False

    def test_custom_thresholds(self):
        """Should use custom thresholds when provided."""
        strict_service = RegressionDetectionService(
            thresholds={"planning": -3.0}  # stricter threshold
        )
        base = self._make_mock_eval({"planning": 80.0}, overall=80.0)
        head = self._make_mock_eval({"planning": 76.0}, overall=76.0)

        report = strict_service.compare(base, head, include_diff=False)

        # -4 is below -3 threshold
        assert report.dimensions["planning"].is_regression is True

    def test_all_dimensions_reported(self):
        """Should report all evaluation dimensions."""
        base = self._make_mock_eval(
            {d: 80.0 for d in ("planning", "tactical", "tool_use", "memory", "replan", "retrieval")},
            overall=80.0,
        )
        head = self._make_mock_eval(
            {d: 80.0 for d in ("planning", "tactical", "tool_use", "memory", "replan", "retrieval")},
            overall=80.0,
        )

        report = self.service.compare(base, head, include_diff=False)

        for dim in ("planning", "tactical", "tool_use", "memory", "replan", "retrieval"):
            assert dim in report.dimensions
            assert report.dimensions[dim].base_score == 80.0
            assert report.dimensions[dim].head_score == 80.0

    def test_missing_scores_default_to_zero(self):
        """Should handle None scores gracefully."""
        base = MagicMock()
        base.id = "base-1"
        base.task_id = "task-1"
        base.overall_score = None
        for d in ("planning", "tactical", "tool_use", "memory", "replan", "retrieval"):
            setattr(base, f"{d}_score", None)

        head = MagicMock()
        head.id = "head-1"
        head.task_id = "task-1"
        head.overall_score = None
        for d in ("planning", "tactical", "tool_use", "memory", "replan", "retrieval"):
            setattr(head, f"{d}_score", None)

        report = self.service.compare(base, head, include_diff=False)

        assert report.overall_change == 0.0
        assert report.has_regression is False

    def test_dimension_change_dataclass(self):
        """Should create correct DimensionChange instances."""
        change = DimensionChange(
            dimension="planning",
            base_score=90.0,
            head_score=70.0,
            delta=-20.0,
            is_regression=True,
            threshold=-10.0,
        )

        assert change.dimension == "planning"
        assert change.base_score == 90.0
        assert change.head_score == 70.0
        assert change.delta == -20.0
        assert change.is_regression is True
        assert change.threshold == -10.0

    def test_default_thresholds(self):
        """Should have sensible default thresholds."""
        assert DEFAULT_THRESHOLDS["overall"] == -5.0
        assert DEFAULT_THRESHOLDS["planning"] == -10.0
        assert DEFAULT_THRESHOLDS["tool_use"] == -8.0
