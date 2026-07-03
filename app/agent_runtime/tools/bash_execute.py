"""
bash_execute — Execute Bash commands inside the sandbox container.
"""

from __future__ import annotations

import asyncio
from typing import Any

from docker.models.containers import Container

from app.agent_runtime.tools.base import SandboxTool


class BashExecuteTool(SandboxTool):
    name = "bash_execute"
    description = (
        "Execute a Bash command in the sandbox environment. "
        "Working directory is /workspace. Useful for system commands, "
        "file manipulation, and running scripts."
    )
    parameters_schema = {
        "command": "str — Bash command to execute",
    }

    async def execute(self, container: Container, *, command: str = "", **kwargs: Any) -> str:
        if not command:
            return "Error: No command provided."

        loop = asyncio.get_running_loop()

        exit_code, output = await loop.run_in_executor(
            None,
            lambda: container.exec_run(
                cmd=["bash", "-c", command],
                stdout=True,
                stderr=True,
                demux=True,
                workdir="/workspace",
            ),
        )

        stdout_bytes, stderr_bytes = (b"", b"")
        if isinstance(output, tuple) and len(output) == 2:
            stdout_bytes = output[0] or b""
            stderr_bytes = output[1] or b""
        elif isinstance(output, (bytes, str)):
            stdout_bytes = output if isinstance(output, bytes) else output.encode()

        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")

        parts = []
        if stdout:
            parts.append(f"stdout:\n{stdout}")
        if stderr:
            parts.append(f"stderr:\n{stderr}")
        if exit_code != 0:
            parts.append(f"exit_code: {exit_code}")

        return "\n".join(parts) if parts else "(no output)"
