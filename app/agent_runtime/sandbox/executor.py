"""
SandboxExecutor — reusable one-shot code execution via SessionPool.

Provides the same public interface as the legacy ``app.sandbox.executor``
but delegates container management to the Agent Runtime's ``SessionPool``,
which also powers the multi-step Agent-in-Sandbox workflow.

Execution flow:
  1. Check Redis cache for identical snippets (content-hash key).
  2. Acquire a session from ``SessionPool``.
  3. Write code into the container via ``put_archive`` (tar stream).
  4. Execute with resource limits and timeout.
  5. Collect stdout/stderr/exit_code/duration.
  6. Cache result in Redis.
  7. Release session (destroy + replace).
  8. Fall back gracefully if Docker / pool is unavailable.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import tarfile
import time
from typing import List, Optional

from app.agent_runtime.sandbox.detector import DetectedCodeSnippet
from app.agent_runtime.sandbox.models import ExecutionResult, SandboxLanguage
from app.agent_runtime.sandbox.session_pool import (
    close_session_pool,
    get_session_pool,
    init_session_pool,
    is_session_pool_available,
)
from app.core.cache import cache_get, cache_set
from app.core.config import settings

logger = logging.getLogger(__name__)


# ── Module-level lifecycle (drop-in replacement for legacy sandbox) ──


async def init_sandbox() -> bool:
    """Initialize the sandbox subsystem (delegates to SessionPool init)."""
    return await init_session_pool()


async def close_sandbox() -> None:
    """Shut down the sandbox subsystem (delegates to SessionPool close)."""
    await close_session_pool()


def is_sandbox_available() -> bool:
    """Check if the sandbox subsystem is operational."""
    return is_session_pool_available()


# ── SandboxExecutor ──────────────────────────────────────────────


class SandboxExecutor:
    """Executes code snippets in Docker containers via SessionPool."""

    async def execute(self, snippet: DetectedCodeSnippet) -> ExecutionResult:
        """Execute a single code snippet in a sandboxed container."""
        pool = get_session_pool()
        if not pool or not pool.available:
            return ExecutionResult(
                language=snippet.language,
                error="Sandbox unavailable (Docker not running or image missing)",
                exit_code=-1,
            )

        # ── Cache check ──
        cache_key = self._cache_key(snippet)
        cached = await cache_get(cache_key)
        if cached is not None:
            logger.debug("Sandbox cache hit: %s", cache_key)
            return ExecutionResult(**cached)

        # ── Acquire session ──
        session = await pool.acquire_session(timeout=settings.SANDBOX_ACQUIRE_TIMEOUT)
        if session is None:
            return ExecutionResult(
                language=snippet.language,
                error="Sandbox pool exhausted — could not acquire container",
                exit_code=-1,
            )

        # ── Execute ──
        try:
            result = await self._run_in_session(session, snippet)
        except Exception as e:
            logger.error("Sandbox execution error: %s", e, exc_info=True)
            result = ExecutionResult(
                language=snippet.language,
                error=f"Internal sandbox error: {e}",
                exit_code=-1,
            )
        finally:
            await pool.release_session(session)

        # ── Cache result ──
        await cache_set(cache_key, result.model_dump(), ttl=settings.SANDBOX_CACHE_TTL)
        return result

    async def execute_batch(self, snippets: List[DetectedCodeSnippet]) -> List[ExecutionResult]:
        """Execute multiple snippets concurrently (bounded by pool size)."""
        return await asyncio.gather(*[self.execute(s) for s in snippets])

    # ── Internal ──────────────────────────────────────────────

    async def _run_in_session(self, session: object, snippet: DetectedCodeSnippet) -> ExecutionResult:
        """
        Inject code into the session container, execute, and collect output.

        ``session`` is a ``SandboxSession`` (duck-typed to avoid circular imports
        at the module level — it needs ``container`` and ``container_id`` attrs).
        """
        loop = asyncio.get_running_loop()
        container = session.container  # docker.models.containers.Container

        # Write code file via put_archive (tar stream)
        filename, cmd = self._get_language_command(snippet)
        tar_data = self._make_tar(filename, snippet.code.encode("utf-8"))
        container.put_archive("/tmp", tar_data)

        # Execute with timeout
        start = time.monotonic()
        try:
            exit_code, output = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: container.exec_run(
                        cmd=cmd,
                        stdout=True,
                        stderr=True,
                        demux=True,
                        workdir="/tmp",
                    ),
                ),
                timeout=settings.SANDBOX_TIMEOUT,
            )
        except asyncio.TimeoutError:
            duration_ms = (time.monotonic() - start) * 1000
            return ExecutionResult(
                language=snippet.language,
                exit_code=-1,
                timed_out=True,
                duration_ms=duration_ms,
                stderr=f"Execution timed out after {settings.SANDBOX_TIMEOUT}s",
            )

        duration_ms = (time.monotonic() - start) * 1000

        # docker-py exec_run with demux=True returns (exit_code, (stdout, stderr))
        stdout_bytes, stderr_bytes = (b"", b"")
        if isinstance(output, tuple) and len(output) == 2:
            stdout_bytes = output[0] or b""
            stderr_bytes = output[1] or b""
        elif isinstance(output, (bytes, str)):
            stdout_bytes = output if isinstance(output, bytes) else output.encode()

        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")

        # Truncate output if too large
        output_limit = settings.SANDBOX_OUTPUT_LIMIT
        truncated = False
        if len(stdout) > output_limit:
            stdout = stdout[:output_limit]
            truncated = True
        if len(stderr) > output_limit:
            stderr = stderr[:output_limit]
            truncated = True

        # Check for OOM kill
        oom_killed = False
        try:
            container.reload()
            if container.attrs.get("State", {}).get("OOMKilled", False):
                oom_killed = True
        except Exception:
            pass

        return ExecutionResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            duration_ms=duration_ms,
            timed_out=False,
            oom_killed=oom_killed,
            output_truncated=truncated,
            language=snippet.language,
        )

    @staticmethod
    def _get_language_command(snippet: DetectedCodeSnippet) -> tuple[str, list[str]]:
        """Return (filename, command_list) for the given language."""
        if snippet.language == SandboxLanguage.PYTHON:
            return "script.py", ["python3", "/tmp/script.py"]
        elif snippet.language == SandboxLanguage.BASH:
            return "script.sh", ["bash", "/tmp/script.sh"]
        elif snippet.language == SandboxLanguage.NODE:
            return "script.js", ["node", "/tmp/script.js"]
        return "script.py", ["python3", "/tmp/script.py"]

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
    def _cache_key(snippet: DetectedCodeSnippet) -> str:
        """Generate a deterministic cache key from language + code content."""
        content = f"{snippet.language.value}:{snippet.code}"
        h = hashlib.sha256(content.encode()).hexdigest()[:20]
        return f"sandbox:{h}"
