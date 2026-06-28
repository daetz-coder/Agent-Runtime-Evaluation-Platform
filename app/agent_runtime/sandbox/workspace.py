"""
WorkspaceManager — manage files inside sandbox container's /workspace directory.

Handles:
  - Initial file injection (setup workspace for agent)
  - File read/write during agent execution
  - Workspace state capture (diff) after agent completes
  - Cleanup between sessions
"""

from __future__ import annotations

import io
import logging
import os
import posixpath
import tarfile
from typing import Any, Dict, List

from docker.models.containers import Container

from app.core.tracing import get_tracer

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)

WORKSPACE_ROOT = "/workspace"


class WorkspaceManager:
    """Manage files inside a sandbox container's /workspace directory."""

    # ── Setup ─────────────────────────────────────────────────

    async def setup(self, container: Container, files: Dict[str, str]) -> None:
        """
        Write initial files into the container's /workspace.

        Args:
            container: Docker container object
            files: Dict of {relative_path: content} to write
        """
        if not files:
            return

        with tracer.start_as_current_span("workspace_setup") as span:
            span.set_attribute("file_count", len(files))
            # Group files into a single tar archive for efficiency
            tar_data = self._make_multi_file_tar(files)
            await self._put_archive(container, WORKSPACE_ROOT, tar_data)
            logger.info(
                "Workspace setup: %d files written to container %s",
                len(files),
                container.id[:12],
            )

    # ── File Operations ───────────────────────────────────────

    async def read_file(self, container: Container, path: str) -> str:
        """
        Read a file from the container's /workspace.

        Args:
            container: Docker container object
            path: Relative path within /workspace

        Returns:
            File content as string

        Raises:
            FileNotFoundError: If the file doesn't exist
        """
        with tracer.start_as_current_span("workspace_read_file") as span:
            span.set_attribute("path", path)
            full_path = self._resolve_path(path)

            loop = __import__("asyncio").get_event_loop()
            try:
                data, stat = await loop.run_in_executor(None, lambda: container.get_archive(full_path))
            except Exception as e:
                span.set_attribute("error", "file_not_found")
                raise FileNotFoundError(f"File not found: {full_path}") from e

            # Extract content from tar archive
            content = self._extract_from_tar(data)
            span.set_attribute("content_length", len(content))
            return content

    async def write_file(self, container: Container, path: str, content: str) -> None:
        """
        Write a file to the container's /workspace.

        Args:
            container: Docker container object
            path: Relative path within /workspace
            content: File content as string
        """
        with tracer.start_as_current_span("workspace_write_file") as span:
            span.set_attribute("path", path)
            span.set_attribute("content_length", len(content))
            full_path = self._resolve_path(path)
            dir_path = os.path.dirname(full_path)
            filename = os.path.basename(full_path)

            # Ensure parent directory exists
            if dir_path and dir_path != WORKSPACE_ROOT:
                await self._ensure_dir(container, dir_path)

            tar_data = self._make_tar(filename, content.encode("utf-8"))
            await self._put_archive(container, dir_path, tar_data)

    async def list_files(self, container: Container, path: str = "") -> List[Dict[str, Any]]:
        """
        List files in a directory within /workspace.

        Args:
            container: Docker container object
            path: Relative path within /workspace (empty = root)

        Returns:
            List of file info dicts: [{name, size, is_dir}]
        """
        full_path = self._resolve_path(path) if path else WORKSPACE_ROOT

        loop = __import__("asyncio").get_event_loop()
        exit_code, output = await loop.run_in_executor(
            None,
            lambda: container.exec_run(
                cmd=["ls", "-la", "--time-style=+%s", full_path],
                stdout=True,
                stderr=True,
                demux=True,
            ),
        )

        if exit_code != 0:
            return []

        stdout = (output[0] or b"").decode("utf-8", errors="replace")
        return self._parse_ls_output(stdout)

    # ── Capture & Diff ────────────────────────────────────────

    async def capture_workspace_state(self, container: Container) -> Dict[str, Any]:
        """
        Capture the final workspace state after agent execution.

        Returns:
            Dict with file listing, total size, and file count.
        """
        files = await self.list_files(container)
        total_size = sum(f.get("size", 0) for f in files if not f.get("is_dir"))
        file_count = sum(1 for f in files if not f.get("is_dir"))

        return {
            "files": files,
            "total_size_bytes": total_size,
            "file_count": file_count,
        }

    async def capture_file_contents(
        self, container: Container, max_files: int = 20, max_size_per_file: int = 50_000
    ) -> Dict[str, str]:
        """
        Read all files in workspace (up to limits) for evaluation context.

        Returns:
            Dict of {relative_path: content}
        """
        files = await self.list_files(container)
        contents: Dict[str, str] = {}
        count = 0

        for f in files:
            if f.get("is_dir"):
                continue
            if count >= max_files:
                break

            name = f["name"]
            try:
                content = await self.read_file(container, name)
                if len(content) > max_size_per_file:
                    content = content[:max_size_per_file] + "\n... [truncated]"
                contents[name] = content
                count += 1
            except FileNotFoundError:
                continue
            except Exception as e:
                contents[name] = f"[Error reading file: {e}]"
                count += 1

        return contents

    # ── Cleanup ───────────────────────────────────────────────

    async def cleanup(self, container: Container) -> None:
        """Remove all files from /workspace."""
        loop = __import__("asyncio").get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: container.exec_run(
                cmd=["sh", "-c", "rm -rf /workspace/* /workspace/.[!.]*"],
                stdout=True,
                stderr=True,
            ),
        )

    # ── Internal helpers ──────────────────────────────────────

    @staticmethod
    def _resolve_path(path: str) -> str:
        """Resolve a relative path to an absolute /workspace path (POSIX slashes)."""
        # Strip leading slashes and workspace prefix for safety
        clean = path.lstrip("/").replace("..", "")
        if clean.startswith("workspace/"):
            clean = clean[len("workspace/") :]
        # Use posixpath since Docker containers are Linux
        return posixpath.join(WORKSPACE_ROOT, clean)

    @staticmethod
    async def _put_archive(container: Container, path: str, tar_data: bytes) -> None:
        """Put a tar archive into a container path."""
        loop = __import__("asyncio").get_event_loop()
        await loop.run_in_executor(None, lambda: container.put_archive(path, tar_data))

    @staticmethod
    async def _ensure_dir(container: Container, path: str) -> None:
        """Create a directory (and parents) inside the container."""
        loop = __import__("asyncio").get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: container.exec_run(
                cmd=["mkdir", "-p", path],
                stdout=True,
                stderr=True,
            ),
        )

    @staticmethod
    def _make_tar(filename: str, data: bytes) -> bytes:
        """Create a tar archive containing a single file."""
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            info = tarfile.TarInfo(name=filename)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        return buf.getvalue()

    @staticmethod
    def _make_multi_file_tar(files: Dict[str, str]) -> bytes:
        """Create a tar archive containing multiple files (with subdirectory support)."""
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            for path, content in files.items():
                data = content.encode("utf-8")
                # Create parent directories if needed
                parts = path.split("/")
                if len(parts) > 1:
                    for i in range(1, len(parts)):
                        dir_name = "/".join(parts[:i]) + "/"
                        try:
                            tar.getmember(dir_name)
                        except KeyError:
                            dir_info = tarfile.TarInfo(name=dir_name)
                            dir_info.type = tarfile.DIRTYPE
                            tar.addfile(dir_info)
                info = tarfile.TarInfo(name=path)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
        return buf.getvalue()

    @staticmethod
    def _extract_from_tar(tar_data: bytes) -> str:
        """Extract the first file's content from a tar archive."""
        # Docker get_archive returns a tar stream (may be a generator)
        if hasattr(tar_data, "read"):
            raw = tar_data.read()
        elif isinstance(tar_data, (bytes, bytearray)):
            raw = bytes(tar_data)
        else:
            # Generator (docker-py sometimes returns this)
            chunks = []
            for chunk in tar_data:
                chunks.append(chunk)
            raw = b"".join(chunks)

        buf = io.BytesIO(raw)
        with tarfile.open(fileobj=buf, mode="r") as tar:
            members = tar.getmembers()
            for member in members:
                if member.isfile():
                    f = tar.extractfile(member)
                    if f:
                        return f.read().decode("utf-8", errors="replace")
        return ""

    @staticmethod
    def _parse_ls_output(output: str) -> List[Dict[str, Any]]:
        """Parse ls -la output into structured file info.

        Handles both epoch timestamps (--time-style=+%s, 7 fields) and
        default date format (9+ fields).
        """
        files = []
        for line in output.strip().split("\n"):
            # Skip total line and empty lines
            if line.startswith("total") or not line.strip():
                continue
            parts = line.split()
            # Minimum 7 fields: perms links owner group size timestamp name
            if len(parts) < 7:
                continue

            name = parts[-1]
            if name in (".", ".."):
                continue

            permissions = parts[0]
            # Skip lines that don't start with valid permission strings
            if len(permissions) < 10:
                continue

            is_dir = permissions.startswith("d")

            # Size is always the 5th field (index 4) in ls output
            try:
                size = int(parts[4])
            except (ValueError, IndexError):
                size = 0

            files.append(
                {
                    "name": name,
                    "size": size,
                    "is_dir": is_dir,
                }
            )
        return files
