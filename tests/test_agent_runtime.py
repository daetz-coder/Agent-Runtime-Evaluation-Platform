"""Tests for the Agent Runtime module (Agent in Sandbox)."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch


# ── TrajectoryRecorder Tests ──────────────────────────────────

class TestTrajectoryRecorder:
    """Tests for TrajectoryRecorder."""

    def test_init_empty(self):
        from app.agent_runtime.trajectory_recorder import TrajectoryRecorder
        rec = TrajectoryRecorder()
        assert rec.get_step_count() == 0
        assert rec.get_trajectory() == []

    def test_record_plan(self):
        from app.agent_runtime.trajectory_recorder import TrajectoryRecorder
        rec = TrajectoryRecorder()
        rec.record_plan({"steps": ["step1", "step2"]})
        assert rec.get_step_count() == 1
        steps = rec.get_trajectory()
        assert steps[0]["action_type"] == "plan"
        assert steps[0]["action_detail"]["steps"] == ["step1", "step2"]
        assert steps[0]["step_number"] == 1

    def test_record_think(self):
        from app.agent_runtime.trajectory_recorder import TrajectoryRecorder
        rec = TrajectoryRecorder()
        rec.record_think("Let me analyze this data...")
        steps = rec.get_trajectory()
        assert len(steps) == 1
        assert steps[0]["action_type"] == "think"
        assert "Let me analyze" in steps[0]["action_detail"]["thought"]

    def test_record_tool_call(self):
        from app.agent_runtime.trajectory_recorder import TrajectoryRecorder
        rec = TrajectoryRecorder()
        rec.record_tool_call(
            tool_name="python_execute",
            tool_input={"code": "print(1+1)"},
            tool_output="2",
            success=True,
            duration_ms=150.5,
        )
        # tool_call creates 2 steps: tool_call + tool_result
        assert rec.get_step_count() == 2
        steps = rec.get_trajectory()
        assert steps[0]["action_type"] == "tool_call"
        assert steps[0]["action_detail"]["tool_name"] == "python_execute"
        assert steps[1]["action_type"] == "tool_result"
        assert steps[1]["action_detail"]["success"] is True
        assert steps[1]["action_detail"]["duration_ms"] == 150.5

    def test_record_tool_call_failure(self):
        from app.agent_runtime.trajectory_recorder import TrajectoryRecorder
        rec = TrajectoryRecorder()
        rec.record_tool_call(
            tool_name="bash_execute",
            tool_input={"command": "rm -rf /"},
            tool_output="Permission denied",
            success=False,
            duration_ms=10,
        )
        steps = rec.get_trajectory()
        assert steps[1]["action_detail"]["success"] is False

    def test_record_replan(self):
        from app.agent_runtime.trajectory_recorder import TrajectoryRecorder
        rec = TrajectoryRecorder()
        rec.record_replan("Original plan failed", {"new_steps": ["retry"]})
        steps = rec.get_trajectory()
        assert steps[0]["action_type"] == "replan"
        assert steps[0]["action_detail"]["reason"] == "Original plan failed"

    def test_record_failure(self):
        from app.agent_runtime.trajectory_recorder import TrajectoryRecorder
        rec = TrajectoryRecorder()
        rec.record_failure("LLM timeout", context={"step": 5})
        steps = rec.get_trajectory()
        assert steps[0]["action_type"] == "failure"
        assert steps[0]["action_detail"]["error"] == "LLM timeout"

    def test_step_numbering_auto_increment(self):
        from app.agent_runtime.trajectory_recorder import TrajectoryRecorder
        rec = TrajectoryRecorder()
        rec.record_plan({"step": "1"})
        rec.record_think("thinking")
        rec.record_tool_call("tool", {"x": 1}, "ok")
        steps = rec.get_trajectory()
        numbers = [s["step_number"] for s in steps]
        assert numbers == [1, 2, 3, 4]  # tool_call adds 2 steps

    def test_reset(self):
        from app.agent_runtime.trajectory_recorder import TrajectoryRecorder
        rec = TrajectoryRecorder()
        rec.record_plan({"x": 1})
        rec.record_think("y")
        assert rec.get_step_count() == 2
        rec.reset()
        assert rec.get_step_count() == 0
        assert rec.get_trajectory() == []

    def test_timestamps_present(self):
        from app.agent_runtime.trajectory_recorder import TrajectoryRecorder
        rec = TrajectoryRecorder()
        rec.record_plan({"x": 1})
        steps = rec.get_trajectory()
        assert "timestamp" in steps[0]
        assert steps[0]["timestamp"] is not None

    def test_truncate_long_strings(self):
        from app.agent_runtime.trajectory_recorder import TrajectoryRecorder
        rec = TrajectoryRecorder()
        long_input = {"data": "x" * 1000}
        rec.record_tool_call("tool", long_input, "ok")
        steps = rec.get_trajectory()
        # The truncated string should be shorter than 1000
        stored = steps[0]["action_detail"]["input"]["data"]
        assert len(stored) < 1000


# ── SandboxTool Tests ─────────────────────────────────────────

class TestSandboxTools:
    """Tests for sandbox tool definitions (without Docker)."""

    def test_tool_registry_has_all_tools(self):
        from app.agent_runtime.tools import TOOL_REGISTRY
        expected = {"python_execute", "bash_execute", "file_read", "file_write", "file_list"}
        assert set(TOOL_REGISTRY.keys()) == expected

    def test_tool_names_match(self):
        from app.agent_runtime.tools import TOOL_REGISTRY
        for name, cls in TOOL_REGISTRY.items():
            tool = cls()
            assert tool.name == name

    def test_tool_has_description(self):
        from app.agent_runtime.tools import TOOL_REGISTRY
        for name, cls in TOOL_REGISTRY.items():
            tool = cls()
            assert tool.description
            assert len(tool.description) > 10

    def test_tool_has_parameters_schema(self):
        from app.agent_runtime.tools import TOOL_REGISTRY
        for name, cls in TOOL_REGISTRY.items():
            tool = cls()
            assert isinstance(tool.parameters_schema, dict)
            assert len(tool.parameters_schema) > 0

    def test_python_execute_schema(self):
        from app.agent_runtime.tools.python_execute import PythonExecuteTool
        tool = PythonExecuteTool()
        assert "code" in tool.parameters_schema

    def test_bash_execute_schema(self):
        from app.agent_runtime.tools.bash_execute import BashExecuteTool
        tool = BashExecuteTool()
        assert "command" in tool.parameters_schema

    def test_file_read_schema(self):
        from app.agent_runtime.tools.file_read import FileReadTool
        tool = FileReadTool()
        assert "path" in tool.parameters_schema

    def test_file_write_schema(self):
        from app.agent_runtime.tools.file_write import FileWriteTool
        tool = FileWriteTool()
        assert "path" in tool.parameters_schema
        assert "content" in tool.parameters_schema

    def test_file_list_schema(self):
        from app.agent_runtime.tools.file_list import FileListTool
        tool = FileListTool()
        assert "path" in tool.parameters_schema


# ── ToolProxy Tests ───────────────────────────────────────────

class TestToolProxy:
    """Tests for ToolProxy validation and routing."""

    def _make_proxy(self, allowed_tools=None):
        from app.agent_runtime.tools.base import ToolProxy
        from app.agent_runtime.trajectory_recorder import TrajectoryRecorder
        mock_container = MagicMock()
        mock_container.id = "test123456789"
        recorder = TrajectoryRecorder()
        allowed = allowed_tools or ["python_execute", "file_read"]
        return ToolProxy(mock_container, allowed, recorder), recorder

    def test_get_available_tools(self):
        proxy, _ = self._make_proxy(["python_execute", "file_read"])
        tools = proxy.get_available_tools()
        names = [t.name for t in tools]
        assert "python_execute" in names
        assert "file_read" in names
        assert "bash_execute" not in names

    def test_get_tool_descriptions(self):
        proxy, _ = self._make_proxy(["python_execute"])
        desc = proxy.get_tool_descriptions()
        assert "python_execute" in desc
        assert "bash_execute" not in desc

    @pytest.mark.asyncio
    async def test_execute_blocked_tool(self):
        proxy, recorder = self._make_proxy(["python_execute"])
        result = await proxy.execute("bash_execute", {"command": "ls"})
        assert "not allowed" in result
        # Should record the failed attempt
        assert recorder.get_step_count() == 2  # tool_call + tool_result

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self):
        proxy, recorder = self._make_proxy(["python_execute", "unknown_tool"])
        result = await proxy.execute("unknown_tool", {"x": 1})
        assert "not found" in result

    def test_empty_tools_list(self):
        from app.agent_runtime.tools.base import ToolProxy
        from app.agent_runtime.trajectory_recorder import TrajectoryRecorder
        mock_container = MagicMock()
        mock_container.id = "test123456789"
        recorder = TrajectoryRecorder()
        proxy = ToolProxy.__new__(ToolProxy)
        proxy.container = mock_container
        proxy.allowed_tools = []
        proxy.recorder = recorder
        proxy._registry = {}
        proxy._load_tools()
        tools = proxy.get_available_tools()
        assert len(tools) == 0


# ── WorkspaceManager Tests ────────────────────────────────────

class TestWorkspaceManager:
    """Tests for WorkspaceManager helper methods (no Docker)."""

    def test_resolve_path_basic(self):
        from app.agent_runtime.sandbox.workspace import WorkspaceManager
        wm = WorkspaceManager()
        assert wm._resolve_path("data.csv") == "/workspace/data.csv"

    def test_resolve_path_strips_leading_slash(self):
        from app.agent_runtime.sandbox.workspace import WorkspaceManager
        wm = WorkspaceManager()
        assert wm._resolve_path("/data.csv") == "/workspace/data.csv"

    def test_resolve_path_strips_workspace_prefix(self):
        from app.agent_runtime.sandbox.workspace import WorkspaceManager
        wm = WorkspaceManager()
        assert wm._resolve_path("workspace/data.csv") == "/workspace/data.csv"

    def test_resolve_path_strips_dotdot(self):
        from app.agent_runtime.sandbox.workspace import WorkspaceManager
        wm = WorkspaceManager()
        assert ".." not in wm._resolve_path("../../etc/passwd")

    def test_make_tar(self):
        import tarfile, io
        from app.agent_runtime.sandbox.workspace import WorkspaceManager
        wm = WorkspaceManager()
        tar_data = wm._make_tar("test.txt", b"hello world")
        buf = io.BytesIO(tar_data)
        with tarfile.open(fileobj=buf, mode="r") as tar:
            members = tar.getmembers()
            assert len(members) == 1
            assert members[0].name == "test.txt"
            assert members[0].size == 11

    def test_make_multi_file_tar(self):
        import tarfile, io
        from app.agent_runtime.sandbox.workspace import WorkspaceManager
        wm = WorkspaceManager()
        files = {"a.txt": "hello", "sub/b.txt": "world"}
        tar_data = wm._make_multi_file_tar(files)
        buf = io.BytesIO(tar_data)
        with tarfile.open(fileobj=buf, mode="r") as tar:
            names = [m.name for m in tar.getmembers()]
            assert "a.txt" in names
            assert "sub/b.txt" in names

    def test_parse_ls_output(self):
        from app.agent_runtime.sandbox.workspace import WorkspaceManager
        wm = WorkspaceManager()
        # Format matches: ls -la --time-style=+%s (epoch timestamps)
        ls_output = """total 8
drwxr-xr-x 2 sandbox sandbox 4096 1700000000 .
drwxr-xr-x 1 root    root    4096 1700000000 ..
-rw-r--r-- 1 sandbox sandbox  100 1700000000 data.csv
-rwxr-xr-x 1 sandbox sandbox  250 1700000000 script.py"""
        files = wm._parse_ls_output(ls_output)
        assert len(files) == 2
        assert files[0]["name"] == "data.csv"
        assert files[0]["size"] == 100
        assert files[0]["is_dir"] is False
        assert files[1]["name"] == "script.py"
        assert files[1]["size"] == 250

    def test_parse_ls_empty(self):
        from app.agent_runtime.sandbox.workspace import WorkspaceManager
        wm = WorkspaceManager()
        assert wm._parse_ls_output("total 0\n") == []


# ── SessionPool Tests ─────────────────────────────────────────

class TestSessionPool:
    """Tests for SessionPool (mocked Docker)."""

    def test_init_state(self):
        from app.agent_runtime.sandbox.session_pool import SessionPool
        pool = SessionPool()
        assert pool.available is False
        assert pool.client is None

    @pytest.mark.asyncio
    async def test_acquire_when_unavailable(self):
        from app.agent_runtime.sandbox.session_pool import SessionPool
        pool = SessionPool()
        session = await pool.acquire_session(timeout=0.1)
        assert session is None


# ── AgentState Tests ──────────────────────────────────────────

class TestAgentState:
    """Tests for AgentState definition."""

    def test_state_keys(self):
        from app.agent_runtime.state import AgentState
        # AgentState is a TypedDict, check it has the expected keys
        assert "goal" in AgentState.__annotations__
        assert "messages" in AgentState.__annotations__
        assert "current_step" in AgentState.__annotations__
        assert "max_steps" in AgentState.__annotations__
        assert "done" in AgentState.__annotations__
        assert "final_answer" in AgentState.__annotations__


# ── Prompts Tests ─────────────────────────────────────────────

class TestPrompts:
    """Tests for agent prompt building."""

    def test_build_system_prompt_basic(self):
        from app.agent_runtime.prompts import build_system_prompt
        prompt = build_system_prompt(
            goal="Analyze data",
            tool_descriptions="- python_execute: Run Python code",
        )
        assert "Analyze data" in prompt
        assert "python_execute" in prompt
        assert "/workspace" in prompt

    def test_build_system_prompt_with_context(self):
        from app.agent_runtime.prompts import build_system_prompt
        prompt = build_system_prompt(
            goal="Fix bug",
            tool_descriptions="- bash_execute: Run commands",
            context="The bug is in auth.py",
        )
        assert "The bug is in auth.py" in prompt

    def test_build_system_prompt_no_context(self):
        from app.agent_runtime.prompts import build_system_prompt
        prompt = build_system_prompt(
            goal="Do something",
            tool_descriptions="- file_read: Read files",
            context="",
        )
        assert "Additional Context" not in prompt


# ── LLM Factory Tests ────────────────────────────────────────

class TestLLMFactory:
    """Tests for LLM factory (without API keys)."""

    def test_unsupported_provider(self):
        from app.agent_runtime.llm_factory import create_llm
        with pytest.raises(ValueError, match="Unsupported"):
            create_llm(provider="nonexistent_provider")

    def test_missing_openai_key(self):
        from app.agent_runtime.llm_factory import create_llm
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            create_llm(provider="openai")

    def test_missing_anthropic_key(self):
        from app.agent_runtime.llm_factory import create_llm
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            create_llm(provider="anthropic")

    def test_missing_deepseek_key(self):
        from app.agent_runtime.llm_factory import create_llm
        with patch("app.agent_runtime.llm_factory.settings") as mock_settings:
            mock_settings.DEEPSEEK_API_KEY = ""
            mock_settings.DEEPSEEK_MODEL = "deepseek-chat"
            with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
                create_llm(provider="deepseek")


# ── Graph Helper Tests ───────────────────────────────────────

class TestGraphHelpers:
    """Tests for graph utility functions."""

    def test_is_final_answer(self):
        from app.agent_runtime.graph import _is_final_answer
        assert _is_final_answer("FINAL ANSWER: The result is 42") is True
        assert _is_final_answer("Task complete. Here is the report.") is True
        assert _is_final_answer("Let me run some code first") is False
        assert _is_final_answer("I need to read the file") is False

    def test_extract_final_answer(self):
        from app.agent_runtime.graph import _extract_final_answer
        assert _extract_final_answer("FINAL ANSWER: The sum is 42") == "The sum is 42"
        assert _extract_final_answer("Some other text") == "Some other text"

    def test_build_langchain_tools(self):
        from app.agent_runtime.graph import _build_langchain_tools
        from app.agent_runtime.tools.base import ToolProxy
        from app.agent_runtime.trajectory_recorder import TrajectoryRecorder
        mock_container = MagicMock()
        mock_container.id = "test123"
        recorder = TrajectoryRecorder()
        proxy = ToolProxy(mock_container, ["python_execute", "file_read"], recorder)
        tools = _build_langchain_tools(proxy)
        assert len(tools) == 2
        names = [t.name for t in tools]
        assert "python_execute" in names
        assert "file_read" in names


# ── AgentRunResult Tests ─────────────────────────────────────

class TestAgentRunResult:
    """Tests for AgentRunResult dataclass."""

    def test_success_result(self):
        from app.agent_runtime.runner import AgentRunResult
        result = AgentRunResult(
            success=True,
            trajectory=[{"step": 1}],
            final_answer="Done",
            steps_taken=3,
            duration_ms=5000,
        )
        assert result.success is True
        assert result.error is None
        assert len(result.trajectory) == 1

    def test_failure_result(self):
        from app.agent_runtime.runner import AgentRunResult
        result = AgentRunResult(
            success=False,
            trajectory=[],
            final_answer="",
            error="Pool exhausted",
        )
        assert result.success is False
        assert result.error == "Pool exhausted"


# ── Config Tests ──────────────────────────────────────────────

class TestAgentRuntimeConfig:
    """Tests that new config settings are properly defined."""

    def test_agent_runtime_defaults(self):
        from app.core.config import settings
        assert hasattr(settings, "AGENT_RUNTIME_ENABLED")
        assert hasattr(settings, "AGENT_MAX_STEPS")
        assert hasattr(settings, "AGENT_TIMEOUT")
        assert hasattr(settings, "SANDBOX_SESSION_POOL_SIZE")
        assert hasattr(settings, "SANDBOX_WORKSPACE_SIZE_MB")
        assert hasattr(settings, "SANDBOX_TOOL_TIMEOUT")
        assert hasattr(settings, "AGENT_DEFAULT_TOOLS")

    def test_default_tools_list(self):
        from app.core.config import settings
        expected = ["python_execute", "bash_execute", "file_read", "file_write", "file_list"]
        assert settings.AGENT_DEFAULT_TOOLS == expected

    def test_max_steps_default(self):
        from app.core.config import settings
        assert settings.AGENT_MAX_STEPS == 20

    def test_timeout_default(self):
        from app.core.config import settings
        assert settings.AGENT_TIMEOUT == 300


# ── Schema Tests ─────────────────────────────────────────────

class TestSandboxSchemas:
    """Tests for new sandbox evaluation schemas."""

    def test_sandbox_eval_request_minimal(self):
        from app.models.schemas import SandboxEvalRequest
        req = SandboxEvalRequest(goal="Analyze data")
        assert req.goal == "Analyze data"
        assert req.model is None
        assert req.tools is None

    def test_sandbox_eval_request_full(self):
        from app.models.schemas import SandboxEvalRequest
        req = SandboxEvalRequest(
            goal="Process sales.csv",
            model="gpt-4",
            provider="openai",
            workspace_files={"sales.csv": "date,amount\n2024-01-01,100"},
            tools=["python_execute", "file_read"],
            max_steps=10,
            temperature=0.5,
        )
        assert req.provider == "openai"
        assert len(req.workspace_files) == 1
        assert req.max_steps == 10

    def test_agent_run_info(self):
        from app.models.schemas import AgentRunInfo
        info = AgentRunInfo(
            success=True,
            steps_taken=5,
            duration_ms=10000,
            final_answer="Done",
        )
        assert info.success is True
        assert info.error is None

    def test_sandbox_eval_response(self):
        from app.models.schemas import SandboxEvalResponse, AgentRunInfo
        from datetime import datetime, timezone
        resp = SandboxEvalResponse(
            task_id="t1",
            evaluation_id="e1",
            status="completed",
            agent_run=AgentRunInfo(
                success=True, steps_taken=3,
                duration_ms=5000, final_answer="ok",
            ),
            created_at=datetime.now(timezone.utc),
        )
        assert resp.task_id == "t1"
        assert resp.agent_run.success is True
