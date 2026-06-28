"""Tests for JudgeService — raw judge prompt/response extraction."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.models.schemas import JudgeRawData
from app.services.judge_service import JudgeService


class TestJudgeService:
    """Tests for the Judge transparency service."""

    def setup_method(self):
        self.service = JudgeService()

    def _make_mock_evaluation(self, feedbacks=None):
        """Helper to create a mock evaluation with feedback data."""
        mock = MagicMock()
        mock.id = "eval-123"
        mock.task_id = "task-456"

        defaults = {
            "planning": {
                "overall": 85.0,
                "coverage": 80,
                "ordering": 90,
                "granularity": 85,
                "completeness": 85,
                "feedback": "Good plan",
                "_judge_raw": [
                    {
                        "prompt": "Evaluate this plan...",
                        "response": '{"coverage": 80, "ordering": 90}',
                        "model": "deepseek-chat",
                        "latency_ms": 1500,
                        "cache_key": "llm:PlanningEvaluator:abc123",
                        "cached": False,
                    }
                ],
            },
            "tactical": {
                "overall": 70.0,
                "relevance": 75,
                "efficiency": 65,
                "correctness": 70,
                "feedback": "Adequate",
            },
        }
        if feedbacks:
            defaults.update(feedbacks)

        mock.planning_feedback = defaults.get("planning")
        mock.tactical_feedback = defaults.get("tactical")
        mock.tool_use_feedback = defaults.get("tool_use", {})
        mock.memory_feedback = defaults.get("memory", {})
        mock.replan_feedback = defaults.get("replan", {})
        mock.retrieval_feedback = defaults.get("retrieval", {})
        return mock

    async def test_get_judge_raw_single_dimension(self):
        """Should return judge raw data for a specific dimension."""
        evaluation = self._make_mock_evaluation()
        result = await self.service.get_judge_raw(evaluation, dimension="planning")

        assert "planning" in result
        assert isinstance(result["planning"], JudgeRawData)
        assert result["planning"].dimension == "planning"
        assert result["planning"].judge_prompt == "Evaluate this plan..."
        assert result["planning"].judge_response == '{"coverage": 80, "ordering": 90}'
        assert result["planning"].judge_model == "deepseek-chat"
        assert result["planning"].score == 85.0
        assert result["planning"].score_breakdown["coverage"] == 80.0

    async def test_get_judge_raw_all_dimensions(self):
        """Should return all dimensions with judge raw data."""
        evaluation = self._make_mock_evaluation()
        result = await self.service.get_judge_raw(evaluation)

        assert "planning" in result
        # tactical has no _judge_raw, so it shouldn't be in result
        assert "tactical" not in result

    async def test_get_judge_raw_missing_dimension(self):
        """Should return empty dict for dimension with no data."""
        evaluation = self._make_mock_evaluation()
        result = await self.service.get_judge_raw(evaluation, dimension="tool_use")

        assert result == {}

    async def test_get_judge_raw_takes_last_call(self):
        """Should take the last judge call when multiple exist."""
        evaluation = self._make_mock_evaluation(
            {
                "planning": {
                    "overall": 90.0,
                    "_judge_raw": [
                        {"prompt": "first prompt", "response": "first response", "model": "gpt-4"},
                        {"prompt": "second prompt", "response": "second response", "model": "gpt-4"},
                        {"prompt": "final prompt", "response": "final response", "model": "gpt-4"},
                    ],
                }
            }
        )
        result = await self.service.get_judge_raw(evaluation, dimension="planning")

        assert result["planning"].judge_prompt == "final prompt"
        assert result["planning"].judge_response == "final response"

    async def test_get_judge_raw_score_breakdown(self):
        """Should extract sub-dimension scores into score_breakdown."""
        evaluation = self._make_mock_evaluation(
            {
                "planning": {
                    "overall": 85,
                    "coverage": 80,
                    "ordering": 90,
                    "granularity": 85,
                    "completeness": 85,
                    "_judge_raw": [{"prompt": "...", "response": "..."}],
                }
            }
        )
        result = await self.service.get_judge_raw(evaluation, dimension="planning")

        breakdown = result["planning"].score_breakdown
        assert breakdown["coverage"] == 80.0
        assert breakdown["ordering"] == 90.0
        assert breakdown["granularity"] == 85.0
        assert "_judge_raw" not in breakdown  # metadata excluded
