"""
SessionPool — long-running Docker container sessions for Agent Runtime.

Unlike the existing ContainerPool (ephemeral, one-shot code execution),
SessionPool provides containers with a writable /workspace directory
for multi-step agent interactions.

Lifecycle:
  1. On startup, create N containers (sleeping, writable /workspace).
  2. Agent Runtime acquires a session for the full agent run.
  3. Agent executes tools, reads/writes files in /workspace.
  4. After agent completes, workspace is captured, container is destroyed and replaced.
  5. On shutdown, all containers are destroyed.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

import docker
from docker.errors import DockerException, NotFound
from docker.models.containers import Container

from app.core.config import settings
from app.core.tracing import get_tracer

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)

_SANDBOX_IMAGE = "agent-eval-sandbox:latest"


@dataclass
class SandboxSession:
    """Represents an active sandbox session with a container and metadata."""

    container_id: str
    container: Container
    created_at: float = 0.0
    workspace_files: list[str] = field(default_factory=list)


class SessionPool:
    """Manages long-running Docker container sessions for Agent Runtime."""

    def __init__(self) -> None:
        self._client: Optional[docker.DockerClient] = None
        self._pool: asyncio.Queue[str] = asyncio.Queue()
        self._active_sessions: dict[str, SandboxSession] = {}
        self._maintenance_task: Optional[asyncio.Task] = None
        self._shutdown = False
        self._available = False

    # ── Lifecycle ─────────────────────────────────────────────

    async def initialize(self) -> bool:
        """
        Connect to Docker and warm the session pool.
        Returns True if the pool is ready, False if Docker is unavailable.
        """
        try:
            self._client = docker.from_env(timeout=5)
            self._client.ping()
        except (DockerException, Exception) as e:
            logger.warning("Docker unavailable — agent runtime disabled: %s", e)
            self._client = None
            return False

        # Verify image exists
        try:
            self._client.images.get(_SANDBOX_IMAGE)
        except NotFound:
            logger.warning(
                "Sandbox image '%s' not found. Build with: docker build -t agent-eval-sandbox -f sandbox.Dockerfile .",
                _SANDBOX_IMAGE,
            )
            self._client = None
            return False

        pool_size = settings.SANDBOX_SESSION_POOL_SIZE

        # Warm pool (create containers sequentially to avoid Docker API burst)
        for _ in range(pool_size):
            cid = await self._create_session_container()
            if cid:
                await self._pool.put(cid)

        # Background maintenance — replace destroyed containers periodically
        self._maintenance_task = asyncio.create_task(self._maintain_pool())
        self._available = True
        logger.info("Session pool ready (%d containers warmed)", self._pool.qsize())
        return True

    async def shutdown(self) -> None:
        """Destroy all containers and disconnect."""
        self._shutdown = True
        if self._maintenance_task:
            self._maintenance_task.cancel()

        # Destroy active sessions
        for session_id, session in list(self._active_sessions.items()):
            self._destroy_container(session.container_id)
        self._active_sessions.clear()

        # Drain pool
        while not self._pool.empty():
            try:
                cid = self._pool.get_nowait()
                self._destroy_container(cid)
            except asyncio.QueueEmpty:
                break

        if self._client:
            self._client.close()
            self._client = None
        self._available = False
        logger.info("Session pool shut down")

    # ── Public API ────────────────────────────────────────────

    @property
    def available(self) -> bool:
        return self._available

    @property
    def client(self) -> Optional[docker.DockerClient]:
        return self._client

    async def acquire_session(self, timeout: float = 0) -> Optional[SandboxSession]:
        """
        Acquire a container session from the pool.
        Returns SandboxSession with a started container, or None on timeout/unavailable.
        """
        if not self._available or self._client is None:
            return None

        acquire_timeout = timeout or settings.SANDBOX_ACQUIRE_TIMEOUT
        try:
            container_id = await asyncio.wait_for(self._pool.get(), timeout=acquire_timeout)
        except asyncio.TimeoutError:
            logger.warning("Session pool exhausted — no container within %.1fs", acquire_timeout)
            return None

        # Start the container and create a session
        try:
            container = self._client.containers.get(container_id)
            container.start()
            session = SandboxSession(
                container_id=container_id,
                container=container,
                created_at=asyncio.get_event_loop().time(),
            )
            self._active_sessions[container_id] = session
            return session
        except Exception as e:
            logger.error("Failed to start session container: %s", e)
            # Put it back or replace it
            await self._replace_container(container_id)
            return None

    async def release_session(self, session: SandboxSession) -> None:
        """Destroy the used session container and create a fresh replacement."""
        # Remove from active sessions
        self._active_sessions.pop(session.container_id, None)
        # Destroy and replace
        await self._replace_container(session.container_id)

    # ── Internal ──────────────────────────────────────────────

    def _create_session_container_sync(self) -> Optional[str]:
        """Synchronous container creation with writable /workspace."""
        if not self._client:
            return None
        try:
            mem_limit = settings.SANDBOX_MEMORY_LIMIT_MB
            workspace_size = settings.SANDBOX_WORKSPACE_SIZE_MB

            container = self._client.containers.create(
                image=_SANDBOX_IMAGE,
                command=["sleep", "infinity"],
                detach=True,
                network_mode="none",
                mem_limit=f"{mem_limit}m",
                cpu_period=100_000,
                cpu_quota=100_000 * settings.SANDBOX_CPU_CORES,
                pids_limit=128,  # More PIDs for multi-step agent work
                security_opt=["no-new-privileges"],
                read_only=True,
                tmpfs={
                    "/tmp": f"size={mem_limit}m",
                    "/workspace": f"size={workspace_size}m",
                },
                cap_drop=["ALL"],
            )
            return container.id
        except Exception as e:
            logger.error("Failed to create session container: %s", e)
            return None

    async def _create_session_container(self) -> Optional[str]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._create_session_container_sync)

    def _destroy_container(self, container_id: str) -> None:
        if not self._client:
            return
        try:
            c = self._client.containers.get(container_id)
            c.kill()
            c.remove(force=True)
        except NotFound:
            pass
        except Exception as e:
            logger.debug("Error destroying container %s: %s", container_id[:12], e)

    async def _replace_container(self, container_id: str) -> None:
        """Destroy old container and create a fresh replacement."""
        self._destroy_container(container_id)
        new_cid = await self._create_session_container()
        if new_cid:
            await self._pool.put(new_cid)

    async def _maintain_pool(self) -> None:
        """Background task: ensure pool stays at target size."""
        while not self._shutdown:
            try:
                await asyncio.sleep(5)
                current = self._pool.qsize()
                target = settings.SANDBOX_SESSION_POOL_SIZE
                if current < target and self._client:
                    for _ in range(target - current):
                        cid = await self._create_session_container()
                        if cid:
                            await self._pool.put(cid)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.debug("Session pool maintenance error", exc_info=True)


# ── Module-level singleton ────────────────────────────────────

_session_pool: Optional[SessionPool] = None


async def init_session_pool() -> bool:
    """Initialize the global session pool. Called from app lifespan."""
    global _session_pool
    if not settings.AGENT_RUNTIME_ENABLED:
        logger.info("Agent runtime disabled by config (AGENT_RUNTIME_ENABLED=false)")
        return False
    _session_pool = SessionPool()
    available = await _session_pool.initialize()
    if not available:
        _session_pool = None
    return available


async def close_session_pool() -> None:
    """Shut down the global session pool."""
    global _session_pool
    if _session_pool:
        await _session_pool.shutdown()
        _session_pool = None


def get_session_pool() -> Optional[SessionPool]:
    """Get the global session pool (None if not initialized)."""
    return _session_pool


def is_session_pool_available() -> bool:
    """Check if the session pool is operational."""
    return _session_pool is not None and _session_pool.available
