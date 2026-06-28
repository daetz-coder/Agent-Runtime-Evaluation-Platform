"""Agent Runtime sandbox subsystem — session pool, workspace, and one-shot execution."""

from app.agent_runtime.sandbox.detector import DetectedCodeSnippet, detect_code_executions
from app.agent_runtime.sandbox.executor import SandboxExecutor, close_sandbox, init_sandbox, is_sandbox_available
from app.agent_runtime.sandbox.models import ExecutionResult, SandboxLanguage
from app.agent_runtime.sandbox.session_pool import SandboxSession, SessionPool
from app.agent_runtime.sandbox.workspace import WorkspaceManager

__all__ = [
    "SessionPool",
    "SandboxSession",
    "WorkspaceManager",
    "SandboxExecutor",
    "ExecutionResult",
    "SandboxLanguage",
    "DetectedCodeSnippet",
    "detect_code_executions",
    "init_sandbox",
    "close_sandbox",
    "is_sandbox_available",
]
