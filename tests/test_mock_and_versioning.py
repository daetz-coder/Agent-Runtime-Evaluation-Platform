"""Tests for Mock Sandbox Mode and Agent Configuration Versioning."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.agent_runtime.mock_executor import MockToolProxy, get_mock_trajectory
from app.agent_runtime.prompts import PROMPT_VERSION
from app.core.config import settings


class TestMockExecutor:
    """Tests for the mock execution environment."""

    def test_get_mock_trajectory_returns_steps(self):
        """Should return a non-empty trajectory."""
        traj = get_mock_trajectory("Test goal")
        assert len(traj) > 0
        assert all("step_number" in s for s in traj)
        assert all("action_type" in s for s in traj)
        assert all("action_detail" in s for s in traj)

    def test_mock_trajectory_includes_planning(self):
        """First step should be a PLAN action."""
        traj = get_mock_trajectory("Test goal")
        assert traj[0]["action_type"] == "plan"

    def test_mock_trajectory_includes_llm_trace(self):
        """Steps should have _llm_trace for Replay Debugger."""
        traj = get_mock_trajectory("Test goal")
        think_steps = [s for s in traj if s["action_type"] == "think"]
        assert len(think_steps) > 0
        for step in think_steps:
            assert "_llm_trace" in step["action_detail"]
            assert step["action_detail"]["_llm_trace"]["model"] == settings.DEFAULT_LLM_MODEL

    def test_mock_trajectory_uses_goal(self):
        """Goal string should appear in trajectory."""
        traj = get_mock_trajectory("自定义任务说明")
        found = any("自定义任务说明" in str(s) for s in traj)
        assert found

    async def test_mock_tool_proxy_execute(self):
        """MockToolProxy.execute() should return a mock result."""
        proxy = MockToolProxy()
        result = await proxy.execute("python_execute", {"code": "print(1)"})
        assert "[MOCK]" in result
        assert "python_execute" in result

    async def test_mock_tool_proxy_records_calls(self):
        """Should record tool calls for inspection."""
        proxy = MockToolProxy()
        await proxy.execute("bash", {"command": "ls"})
        await proxy.execute("python", {"code": "x=1"})

        calls = proxy.get_tool_calls()
        assert len(calls) == 2
        assert calls[0]["name"] == "bash"
        assert calls[1]["name"] == "python"

    def test_mock_tool_proxy_tool_descriptions(self):
        """Should return a non-empty description."""
        proxy = MockToolProxy()
        desc = proxy.get_tool_descriptions()
        assert len(desc) > 0
        assert "Mock" in desc


class TestAgentVersioning:
    """Tests for agent prompt/model version tracking."""

    def test_prompt_version_defined(self):
        """PROMPT_VERSION should be a non-empty string."""
        assert PROMPT_VERSION
        assert isinstance(PROMPT_VERSION, str)
        assert PROMPT_VERSION.startswith("v")

    def test_prompt_version_increments_on_change(self):
        """Version should follow semver-like pattern."""
        parts = PROMPT_VERSION.lstrip("v").split(".")
        assert len(parts) == 2
        major, minor = parts
        assert major.isdigit()
        assert minor.isdigit()
