"""Tests for sandbox code detection and execution models."""

from app.agent_runtime.sandbox.detector import DetectedCodeSnippet, detect_code_executions
from app.agent_runtime.sandbox.models import ExecutionResult, SandboxLanguage


class TestSandboxModels:
    """Tests for ExecutionResult and SandboxLanguage."""

    def test_execution_result_success(self):
        r = ExecutionResult(
            stdout="4\n",
            exit_code=0,
            duration_ms=120,
            language=SandboxLanguage.PYTHON,
        )
        assert r.success is True
        assert "OK" in r.summary()

    def test_execution_result_failure(self):
        r = ExecutionResult(
            stderr="NameError: name 'x' is not defined",
            exit_code=1,
            duration_ms=50,
            language=SandboxLanguage.PYTHON,
        )
        assert r.success is False
        assert "EXIT 1" in r.summary()

    def test_execution_result_timeout(self):
        r = ExecutionResult(
            exit_code=-1,
            timed_out=True,
            duration_ms=30000,
            language=SandboxLanguage.BASH,
        )
        assert r.success is False
        assert "TIMEOUT" in r.summary()

    def test_execution_result_oom(self):
        r = ExecutionResult(
            exit_code=-1,
            oom_killed=True,
            duration_ms=5000,
            language=SandboxLanguage.PYTHON,
        )
        assert "OOM KILLED" in r.summary()

    def test_execution_result_sandbox_error(self):
        r = ExecutionResult(
            exit_code=-1,
            error="Docker daemon down",
            language=SandboxLanguage.PYTHON,
        )
        assert r.success is False
        assert "SANDBOX ERROR" in r.summary()

    def test_output_truncated_flag(self):
        r = ExecutionResult(
            stdout="x" * 100,
            exit_code=0,
            output_truncated=True,
            language=SandboxLanguage.NODE,
        )
        assert r.output_truncated is True


class TestSandboxDetector:
    """Tests for detect_code_executions()."""

    def test_detect_python_tool(self):
        calls = [
            {"step": 1, "tool": "run_python", "input": {"code": "print(42)"}, "output": "42"},
        ]
        snippets = detect_code_executions(calls)
        assert len(snippets) == 1
        assert snippets[0].language == SandboxLanguage.PYTHON
        assert snippets[0].code == "print(42)"
        assert snippets[0].original_output == "42"

    def test_detect_bash_tool(self):
        calls = [
            {"step": 2, "tool": "bash", "input": {"command": "ls -la"}, "output": "total 0"},
        ]
        snippets = detect_code_executions(calls)
        assert len(snippets) == 1
        assert snippets[0].language == SandboxLanguage.BASH
        assert snippets[0].code == "ls -la"

    def test_detect_node_tool(self):
        calls = [
            {"step": 3, "tool": "execute_js", "input": {"code": "console.log(1)"}, "output": "1"},
        ]
        snippets = detect_code_executions(calls)
        assert len(snippets) == 1
        assert snippets[0].language == SandboxLanguage.NODE

    def test_ignore_non_code_tools(self):
        calls = [
            {"step": 1, "tool": "search_code", "input": {"query": "auth"}, "output": "..."},
            {"step": 2, "tool": "read_file", "input": {"path": "/foo.py"}, "output": "..."},
            {"step": 3, "tool": "list_directory", "input": {"path": "/"}, "output": "..."},
        ]
        snippets = detect_code_executions(calls)
        assert len(snippets) == 0

    def test_mixed_tools(self):
        calls = [
            {"step": 1, "tool": "search_code", "input": {"query": "x"}, "output": "..."},
            {"step": 2, "tool": "run_python", "input": {"code": "print(1)"}, "output": "1"},
            {"step": 3, "tool": "read_file", "input": {"path": "a.py"}, "output": "..."},
            {"step": 4, "tool": "shell", "input": {"command": "echo hi"}, "output": "hi"},
        ]
        snippets = detect_code_executions(calls)
        assert len(snippets) == 2
        assert snippets[0].language == SandboxLanguage.PYTHON
        assert snippets[1].language == SandboxLanguage.BASH

    def test_empty_input_skipped(self):
        calls = [
            {"step": 1, "tool": "run_python", "input": {"code": ""}, "output": ""},
            {"step": 2, "tool": "run_python", "input": {}, "output": ""},
        ]
        snippets = detect_code_executions(calls)
        assert len(snippets) == 0

    def test_string_input(self):
        """Some tools pass input as a plain string instead of dict."""
        calls = [
            {"step": 1, "tool": "run_python", "input": "print('hello')", "output": "hello"},
        ]
        snippets = detect_code_executions(calls)
        assert len(snippets) == 1
        assert snippets[0].code == "print('hello')"

    def test_various_python_names(self):
        for name in ["run_python", "execute_python", "python_repl", "run_code", "execute_code"]:
            calls = [{"step": 1, "tool": name, "input": {"code": "x=1"}, "output": ""}]
            snippets = detect_code_executions(calls)
            assert len(snippets) == 1, f"Failed to detect {name}"
            assert snippets[0].language == SandboxLanguage.PYTHON

    def test_various_bash_names(self):
        for name in ["bash", "shell", "run_shell", "run_bash", "execute_shell", "terminal", "run_command"]:
            calls = [{"step": 1, "tool": name, "input": {"command": "ls"}, "output": ""}]
            snippets = detect_code_executions(calls)
            assert len(snippets) == 1, f"Failed to detect {name}"
            assert snippets[0].language == SandboxLanguage.BASH

    def test_empty_tool_list(self):
        assert detect_code_executions([]) == []

    def test_missing_tool_name(self):
        calls = [{"step": 1, "tool": "", "input": {"code": "x=1"}, "output": ""}]
        assert detect_code_executions(calls) == []

    def test_preserves_step_and_output(self):
        calls = [
            {"step": 42, "tool": "run_python", "input": {"code": "1+1"}, "output": "2"},
        ]
        snippets = detect_code_executions(calls)
        assert snippets[0].step == 42
        assert snippets[0].original_output == "2"


class TestSandboxAvailability:
    """Test graceful degradation when Docker is unavailable."""

    def test_sandbox_unavailable_by_default(self):
        """Without init_sandbox(), is_sandbox_available() should be False."""
        from app.agent_runtime.sandbox.executor import is_sandbox_available

        assert is_sandbox_available() is False

    def test_executor_returns_error_when_unavailable(self):
        """SandboxExecutor.execute() should return error result when unavailable."""
        import asyncio

        from app.agent_runtime.sandbox.executor import SandboxExecutor

        snippet = DetectedCodeSnippet(
            step=1,
            tool_name="run_python",
            language=SandboxLanguage.PYTHON,
            code="print(1)",
            original_output="1",
        )

        async def run():
            executor = SandboxExecutor()
            return await executor.execute(snippet)

        result = asyncio.run(run())
        assert result.success is False
        assert result.error is not None
        assert "unavailable" in result.error.lower()


class TestSandboxCacheKey:
    """Test cache key generation."""

    def test_deterministic_key(self):
        from app.agent_runtime.sandbox.executor import SandboxExecutor

        s = DetectedCodeSnippet(
            step=1,
            tool_name="run_python",
            language=SandboxLanguage.PYTHON,
            code="print(1)",
            original_output="1",
        )
        key1 = SandboxExecutor._cache_key(s)
        key2 = SandboxExecutor._cache_key(s)
        assert key1 == key2
        assert key1.startswith("sandbox:")

    def test_different_code_different_key(self):
        from app.agent_runtime.sandbox.executor import SandboxExecutor

        s1 = DetectedCodeSnippet(
            step=1,
            tool_name="run_python",
            language=SandboxLanguage.PYTHON,
            code="print(1)",
            original_output="1",
        )
        s2 = DetectedCodeSnippet(
            step=1,
            tool_name="run_python",
            language=SandboxLanguage.PYTHON,
            code="print(2)",
            original_output="2",
        )
        assert SandboxExecutor._cache_key(s1) != SandboxExecutor._cache_key(s2)

    def test_different_language_different_key(self):
        from app.agent_runtime.sandbox.executor import SandboxExecutor

        s1 = DetectedCodeSnippet(
            step=1,
            tool_name="run_python",
            language=SandboxLanguage.PYTHON,
            code="print(1)",
            original_output="1",
        )
        s2 = DetectedCodeSnippet(
            step=1,
            tool_name="run_node",
            language=SandboxLanguage.NODE,
            code="print(1)",
            original_output="1",
        )
        assert SandboxExecutor._cache_key(s1) != SandboxExecutor._cache_key(s2)


class TestLanguageCommand:
    """Test language-to-command mapping."""

    def test_python_command(self):
        from app.agent_runtime.sandbox.executor import SandboxExecutor

        s = DetectedCodeSnippet(
            step=1,
            tool_name="run_python",
            language=SandboxLanguage.PYTHON,
            code="x=1",
            original_output="",
        )
        filename, cmd = SandboxExecutor._get_language_command(s)
        assert filename == "script.py"
        assert cmd == ["python3", "/tmp/script.py"]

    def test_bash_command(self):
        from app.agent_runtime.sandbox.executor import SandboxExecutor

        s = DetectedCodeSnippet(
            step=1,
            tool_name="bash",
            language=SandboxLanguage.BASH,
            code="ls",
            original_output="",
        )
        filename, cmd = SandboxExecutor._get_language_command(s)
        assert filename == "script.sh"
        assert cmd == ["bash", "/tmp/script.sh"]

    def test_node_command(self):
        from app.agent_runtime.sandbox.executor import SandboxExecutor

        s = DetectedCodeSnippet(
            step=1,
            tool_name="run_node",
            language=SandboxLanguage.NODE,
            code="console.log(1)",
            original_output="",
        )
        filename, cmd = SandboxExecutor._get_language_command(s)
        assert filename == "script.js"
        assert cmd == ["node", "/tmp/script.js"]
