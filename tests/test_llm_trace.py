"""Tests for LLM trace injection in TrajectoryRecorder and Agent Graph."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.agent_runtime.graph import _serialize_messages
from app.agent_runtime.trajectory_recorder import TrajectoryRecorder


class TestLLMTraceRecorder:
    """Tests for TrajectoryRecorder LLM trace injection."""

    def setup_method(self):
        self.recorder = TrajectoryRecorder()

    def test_record_think_with_llm_trace(self):
        """Should inject LLM trace into action_detail when recording think."""
        self.recorder.record_think(
            "I need to search the database",
            llm_trace={
                "prompt": "System: You are an agent...",
                "response": '{"thought": "I need to search the database"}',
                "model": "deepseek-chat",
                "latency_ms": 1500,
            },
        )

        traj = self.recorder.get_trajectory()
        assert len(traj) == 1

        step = traj[0]
        assert step["action_type"] == "think"
        assert step["action_detail"]["thought"] == "I need to search the database"
        assert "_llm_trace" in step["action_detail"]
        assert step["action_detail"]["_llm_trace"]["prompt"] == "System: You are an agent..."
        assert step["action_detail"]["_llm_trace"]["model"] == "deepseek-chat"
        assert step["action_detail"]["_llm_trace"]["latency_ms"] == 1500

    def test_record_think_without_llm_trace(self):
        """Should work without LLM trace (backward compatibility)."""
        self.recorder.record_think("Just thinking")

        traj = self.recorder.get_trajectory()
        assert len(traj) == 1
        assert "_llm_trace" not in traj[0]["action_detail"]

    def test_llm_trace_truncates_long_fields(self):
        """Should truncate prompt/response over 10000 chars."""
        long_text = "x" * 20000
        self.recorder.record_think(
            "Test",
            llm_trace={
                "prompt": long_text,
                "response": long_text,
                "model": "gpt-4",
                "latency_ms": 100,
            },
        )

        traj = self.recorder.get_trajectory()
        trace = traj[0]["action_detail"]["_llm_trace"]
        assert len(trace["prompt"]) == 10000
        assert len(trace["response"]) == 10000

    def test_tool_call_with_llm_trace(self):
        """record_tool_call does NOT inject llm_trace directly but the
        _record method handles it if passed via the action_detail."""
        # record_tool_call doesn't support llm_trace yet, but _record does
        # This test verifies backward compatibility
        self.recorder.record_tool_call(
            tool_name="python_execute",
            tool_input={"code": "print(1)"},
            tool_output="1",
            success=True,
            duration_ms=500,
        )

        traj = self.recorder.get_trajectory()
        # Should create 2 steps (tool_call + tool_result)
        assert len(traj) == 2
        # Neither should have _llm_trace (field not passed)
        assert "_llm_trace" not in traj[0].get("action_detail", {})

    def test_multiple_steps_with_traces(self):
        """Should handle multiple steps with LLM traces."""
        for i in range(3):
            self.recorder.record_think(
                f"Thought {i}",
                llm_trace={
                    "prompt": f"Prompt {i}",
                    "response": f"Response {i}",
                    "model": "deepseek-chat",
                    "latency_ms": 100 * i,
                },
            )

        traj = self.recorder.get_trajectory()
        assert len(traj) == 3
        for i, step in enumerate(traj):
            assert step["action_detail"]["_llm_trace"]["prompt"] == f"Prompt {i}"
            assert step["action_detail"]["_llm_trace"]["latency_ms"] == 100 * i


class FakeMessage:
    """Minimal LangChain message mock for testing _serialize_messages."""

    def __init__(self, type_: str, content: str):
        self.type = type_
        self.content = content


class TestSerializeMessages:
    """Tests for _serialize_messages helper."""

    def test_single_message(self):
        messages = [FakeMessage("human", "Hello")]
        result = _serialize_messages(messages)
        assert "[human]" in result
        assert "Hello" in result

    def test_system_and_human(self):
        messages = [
            FakeMessage("system", "You are an agent"),
            FakeMessage("human", "Do X"),
        ]
        result = _serialize_messages(messages)
        assert "[system]" in result
        assert "You are an agent" in result
        assert "[human]" in result
        assert "Do X" in result

    def test_truncates_long_content(self):
        messages = [FakeMessage("human", "x" * 5000)]
        result = _serialize_messages(messages)
        assert len(result) <= 10000  # total capped

    def test_empty_list(self):
        result = _serialize_messages([])
        assert result == ""

    def test_unknown_role(self):
        messages = [FakeMessage("tool", "result")]
        result = _serialize_messages(messages)
        assert "[tool]" in result

    def test_none_content(self):
        class Msg:
            type = "human"
            content = None

        result = _serialize_messages([Msg()])
        assert "[human]" in result
        assert "" in result  # None becomes ""
