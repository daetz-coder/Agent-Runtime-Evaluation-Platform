"""
file_write — Write a file to the sandbox container's /workspace.
"""

from __future__ import annotations

import asyncio
import io
import os
import posixpath
import tarfile
from typing import Any

from docker.models.containers import Container

from app.agent_runtime.tools.base import SandboxTool

WORKSPACE_ROOT = "/workspace"


class FileWriteTool(SandboxTool):
    name = "file_write"
    description = (
        "Write content to a file in the workspace. Creates parent directories if needed. Overwrites existing files."
    )
    parameters_schema = {
        "path": "str — File path relative to /workspace",
        "content": "str — Content to write to the file",
    }

    async def execute(self, container: Container, *, path: str = "", content: str = "", **kwargs: Any) -> str:
        if not path:
            return "Error: No file path provided."

        full_path = self._resolve_path(path)
        dir_path = os.path.dirname(full_path)
        filename = os.path.basename(full_path)
        loop = asyncio.get_running_loop()

        # Ensure parent directory exists
        if dir_path and dir_path != WORKSPACE_ROOT:
            await loop.run_in_executor(
                None,
                lambda: container.exec_run(
                    cmd=["mkdir", "-p", dir_path],
                    stdout=True,
                    stderr=True,
                ),
            )

        # Write file via tar archive
        tar_data = self._make_tar(filename, content.encode("utf-8"))
        await loop.run_in_executor(None, lambda: container.put_archive(dir_path, tar_data))

        return f"File written: {path} ({len(content)} bytes)"

    @staticmethod
    def _resolve_path(path: str) -> str:
        clean = path.lstrip("/")
        if clean.startswith("workspace/"):
            clean = clean[len("workspace/"):]
        resolved = posixpath.normpath(posixpath.join(WORKSPACE_ROOT, clean))
        if not resolved.startswith(WORKSPACE_ROOT):
            resolved = WORKSPACE_ROOT
        return resolved

    @staticmethod
    def _make_tar(filename: str, data: bytes) -> bytes:
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            info = tarfile.TarInfo(name=filename)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        return buf.getvalue()
