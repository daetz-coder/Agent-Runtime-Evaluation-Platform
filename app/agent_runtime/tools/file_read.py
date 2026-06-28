"""
file_read — Read a file from the sandbox container's /workspace.
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


class FileReadTool(SandboxTool):
    name = "file_read"
    description = (
        "Read the contents of a file from the workspace. "
        "Provide a path relative to /workspace."
    )
    parameters_schema = {
        "path": "str — File path relative to /workspace",
    }

    async def execute(self, container: Container, *, path: str = "", **kwargs: Any) -> str:
        if not path:
            return "Error: No file path provided."

        full_path = self._resolve_path(path)
        loop = asyncio.get_event_loop()

        try:
            data, stat = await loop.run_in_executor(
                None, lambda: container.get_archive(full_path)
            )
        except Exception:
            return f"Error: File not found: {path}"

        content = self._extract_from_tar(data)
        if not content:
            return f"Error: Could not read file: {path}"

        # Truncate very large files
        if len(content) > 50_000:
            return content[:50_000] + f"\n... [truncated, file is {len(content)} chars]"
        return content

    @staticmethod
    def _resolve_path(path: str) -> str:
        clean = path.lstrip("/").replace("..", "")
        return posixpath.join(WORKSPACE_ROOT, clean)

    @staticmethod
    def _extract_from_tar(tar_data) -> str:
        if hasattr(tar_data, "read"):
            raw = tar_data.read()
        elif isinstance(tar_data, (bytes, bytearray)):
            raw = bytes(tar_data)
        else:
            chunks = list(tar_data)
            raw = b"".join(chunks)

        buf = io.BytesIO(raw)
        with tarfile.open(fileobj=buf, mode="r") as tar:
            for member in tar.getmembers():
                if member.isfile():
                    f = tar.extractfile(member)
                    if f:
                        return f.read().decode("utf-8", errors="replace")
        return ""
