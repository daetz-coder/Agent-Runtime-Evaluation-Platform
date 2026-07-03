"""
file_list — List files and directories in the sandbox container's /workspace.
"""

from __future__ import annotations

import asyncio
import posixpath
from typing import Any

from docker.models.containers import Container

from app.agent_runtime.tools.base import SandboxTool

WORKSPACE_ROOT = "/workspace"


class FileListTool(SandboxTool):
    name = "file_list"
    description = (
        "List files and directories in the workspace. Provide a path relative to /workspace, or leave empty for root."
    )
    parameters_schema = {
        "path": "str — Directory path relative to /workspace (default: root)",
    }

    async def execute(self, container: Container, *, path: str = "", **kwargs: Any) -> str:
        full_path = self._resolve_path(path) if path else WORKSPACE_ROOT
        loop = asyncio.get_running_loop()

        exit_code, output = await loop.run_in_executor(
            None,
            lambda: container.exec_run(
                cmd=["ls", "-la", full_path],
                stdout=True,
                stderr=True,
                demux=True,
            ),
        )

        stdout_bytes, stderr_bytes = (b"", b"")
        if isinstance(output, tuple) and len(output) == 2:
            stdout_bytes = output[0] or b""
            stderr_bytes = output[1] or b""

        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")

        if exit_code != 0:
            return f"Error listing {path or '/'}: {stderr}" if stderr else f"Error: directory not found: {path}"

        return stdout if stdout else "(empty directory)"

    @staticmethod
    def _resolve_path(path: str) -> str:
        clean = path.lstrip("/")
        # Strip leading "workspace/" prefix to avoid /workspace/workspace/...
        if clean.startswith("workspace/"):
            clean = clean[len("workspace/"):]
        resolved = posixpath.normpath(posixpath.join(WORKSPACE_ROOT, clean))
        if not resolved.startswith(WORKSPACE_ROOT):
            resolved = WORKSPACE_ROOT
        return resolved
