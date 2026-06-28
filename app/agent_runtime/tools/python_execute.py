"""
python_execute — Execute Python code inside the sandbox container.

Writes code to /workspace/script.py, runs it, returns stdout/stderr.
"""

from __future__ import annotations

import asyncio
import io
import tarfile
from typing import Any

from docker.models.containers import Container

from app.agent_runtime.tools.base import SandboxTool
from app.core.config import settings


class PythonExecuteTool(SandboxTool):
    name = "python_execute"
    description = (
        "Execute Python code in an isolated sandbox environment. "
        "The code runs in /workspace and can read/write files there. "
        "Pre-installed packages: numpy, pandas, requests, beautifulsoup4, "
        "sympy, Pillow, matplotlib, scikit-learn, openpyxl."
    )
    parameters_schema = {
        "code": "str — Python code to execute",
    }

    async def execute(self, container: Container, *, code: str = "", **kwargs: Any) -> str:
        if not code:
            return "Error: No code provided."

        loop = asyncio.get_event_loop()

        # Write code to /workspace/script.py
        tar_data = self._make_tar("script.py", code.encode("utf-8"))
        await loop.run_in_executor(
            None, lambda: container.put_archive("/workspace", tar_data)
        )

        # Execute
        exit_code, output = await loop.run_in_executor(
            None,
            lambda: container.exec_run(
                cmd=["python3", "/workspace/script.py"],
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

        # Build result
        parts = []
        if stdout:
            parts.append(f"stdout:\n{stdout}")
        if stderr:
            parts.append(f"stderr:\n{stderr}")
        if exit_code != 0:
            parts.append(f"exit_code: {exit_code}")

        return "\n".join(parts) if parts else "(no output)"

    @staticmethod
    def _make_tar(filename: str, data: bytes) -> bytes:
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            info = tarfile.TarInfo(name=filename)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        return buf.getvalue()
