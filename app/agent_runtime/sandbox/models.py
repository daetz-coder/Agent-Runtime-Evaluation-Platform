"""Pydantic models for sandbox execution and session management."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SandboxLanguage(str, Enum):
    """Supported sandbox execution languages."""

    PYTHON = "python"
    BASH = "bash"
    NODE = "node"


class ExecutionResult(BaseModel):
    """Result of executing a code snippet in the sandbox."""

    stdout: str = Field(default="", description="Standard output (truncated to OUTPUT_LIMIT)")
    stderr: str = Field(default="", description="Standard error (truncated to OUTPUT_LIMIT)")
    exit_code: int = Field(default=-1, description="Process exit code (-1 = sandbox error)")
    duration_ms: float = Field(default=0, description="Wall-clock execution time in milliseconds")
    timed_out: bool = Field(default=False, description="True if execution was killed by timeout")
    oom_killed: bool = Field(default=False, description="True if container was OOM-killed")
    output_truncated: bool = Field(default=False, description="True if stdout/stderr exceeded limit")
    language: SandboxLanguage = Field(description="Language the snippet was executed as")
    error: Optional[str] = Field(default=None, description="Sandbox-level error (None = success)")

    @property
    def success(self) -> bool:
        """True if the code executed without errors."""
        return self.exit_code == 0 and self.error is None

    def summary(self) -> str:
        """Short summary for the LLM judge prompt."""
        if self.error:
            return f"[SANDBOX ERROR] {self.error}"

        status = "OK" if self.success else f"EXIT {self.exit_code}"
        if self.timed_out:
            status = "TIMEOUT (30s)"
        if self.oom_killed:
            status = "OOM KILLED"

        parts = [f"[{status}]"]
        if self.stdout:
            parts.append(f"stdout: {self.stdout[:500]}")
        if self.stderr:
            parts.append(f"stderr: {self.stderr[:300]}")
        parts.append(f"({self.duration_ms:.0f}ms)")
        return " | ".join(parts)
