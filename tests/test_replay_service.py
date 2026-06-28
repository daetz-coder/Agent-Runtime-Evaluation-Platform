"""Tests for ReplayService — step-by-step replay debug data."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.models.schemas import LLMTraceInfo, ReplayResponse
from app.services.replay_service import ReplayService


class TestReplayService:
    """Tests for the Replay debugger service."""

    def setup_method(self):
        self.service = ReplayService()

    async def test_replay_assembles_steps(self):
        """Should assemble replay data from trajectory steps."""
        mock_eval = MagicMock()
        mock_eval.task_id = "task-123"
        mock_eval.id = "eval-456"

        trajectory = [
            {
                "step_number": 1,
                "action_type": "plan",
                "action_detail": {
                    "plan": "Do X",
                    "_llm_trace": {
                        "prompt": "System: You are...",
                        "response": '{"plan": "Do X"}',
                        "model": "deepseek-chat",
                        "latency_ms": 1200,
                    },
                },
                "observation": None,
            },
            {
                "step_number": 2,
                "action_type": "tool_call",
                "action_detail": {
                    "tool": "python_execute",
                    "code": "print(1)",
                    "_llm_trace": {
                        "prompt": "Previous steps...",
                        "response": '{"tool": "python_execute"}',
                        "model": "deepseek-chat",
                        "latency_ms": 800,
                    },
                },
                "observation": "1",
            },
        ]

        result = await self.service.get_replay(mock_eval, trajectory, "Test goal")

        assert isinstance(result, ReplayResponse)
        assert result.task_id == "task-123"
        assert result.evaluation_id == "eval-456"
        assert result.goal == "Test goal"
        assert result.step_count == 2

        step1 = result.steps[0]
        assert step1.step_number == 1
        assert step1.action_type == "plan"
        assert step1.llm_prompt == "System: You are..."
        assert step1.llm_response == '{"plan": "Do X"}'
        assert step1.llm_model == "deepseek-chat"
        assert step1.latency_ms == 1200.0

        step2 = result.steps[1]
        assert step2.step_number == 2
        assert step2.action_type == "tool_call"
        assert step2.llm_prompt == "Previous steps..."

    async def test_replay_without_llm_trace(self):
        """Should handle steps without _llm_trace gracefully."""
        mock_eval = MagicMock()
        mock_eval.task_id = "task-123"
        mock_eval.id = "eval-456"

        trajectory = [
            {
                "step_number": 1,
                "action_type": "plan",
                "action_detail": {"plan": "Do X"},
                "observation": None,
            }
        ]

        result = await self.service.get_replay(mock_eval, trajectory, "No trace")

        assert result.step_count == 1
        step = result.steps[0]
        assert step.llm_prompt == ""
        assert step.llm_response == ""
        assert step.llm_model == "unknown"
        assert step.latency_ms == 0.0

    async def test_replay_empty_trajectory(self):
        """Should handle empty trajectory."""
        mock_eval = MagicMock()
        mock_eval.task_id = "task-1"
        mock_eval.id = "eval-1"

        result = await self.service.get_replay(mock_eval, [], "Empty")

        assert result.step_count == 0
        assert result.steps == []

    def test_inject_llm_trace(self):
        """Should inject LLM trace into action_detail."""
        detail = {"tool": "bash", "command": "ls"}
        result = ReplayService.inject_llm_trace(
            detail,
            prompt="System: ...",
            response='{"command": "ls"}',
            model="gpt-4",
            latency_ms=500,
        )

        assert result["_llm_trace"]["prompt"] == "System: ..."
        assert result["_llm_trace"]["model"] == "gpt-4"
        assert result["_llm_trace"]["latency_ms"] == 500
        assert result["tool"] == "bash"  # Original data preserved

    def test_inject_truncates_long_prompt(self):
        """Should truncate prompt/response over 10000 chars."""
        long_text = "x" * 20000
        detail = {"tool": "test"}
        result = ReplayService.inject_llm_trace(detail, prompt=long_text, response=long_text)

        assert len(result["_llm_trace"]["prompt"]) == 10000
        assert len(result["_llm_trace"]["response"]) == 10000
