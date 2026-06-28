"""
Container pool — pre-warmed Docker containers for low-latency code execution.

Lifecycle:
  1. On startup, create N containers (created but sleeping).
  2. When a snippet needs execution, acquire a container from the pool.
  3. Start the container, exec the code, collect results.
  4. Destroy the container and create a fresh replacement.
  5. On shutdown, destroy all containers.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import docker
from docker.errors import DockerException, NotFound

from app.core.config import settings

logger = logging.getLogger(__name__)

_SANDBOX_IMAGE = "agent-eval-sandbox:latest"


class ContainerPool:
    """Manages a pool of pre-created Docker containers."""

    def __init__(self) -> None:
        self._client: Optional[docker.DockerClient] = None
        self._pool: asyncio.Queue[str] = asyncio.Queue()
        self._maintenance_task: Optional[asyncio.Task] = None
        self._shutdown = False
        self._available = False

    # ── Lifecycle ─────────────────────────────────────────────

    async def initialize(self) -> bool:
        """
        Connect to Docker and warm the container pool.
        Returns True if the pool is ready, False if Docker is unavailable.
        """
        try:
            self._client = docker.from_env(timeout=5)
            self._client.ping()
        except (DockerException, Exception) as e:
            logger.warning("Docker unavailable — sandbox disabled: %s", e)
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

        pool_size = settings.SANDBOX_POOL_SIZE

        # Warm pool (create containers sequentially to avoid Docker API burst)
        for _ in range(pool_size):
            cid = await self._create_container()
            if cid:
                await self._pool.put(cid)

        # Background maintenance — replace destroyed containers periodically
        self._maintenance_task = asyncio.create_task(self._maintain_pool())
        self._available = True
        logger.info("Sandbox pool ready (%d containers warmed)", self._pool.qsize())
        return True

    async def shutdown(self) -> None:
        """Destroy all containers and disconnect."""
        self._shutdown = True
        if self._maintenance_task:
            self._maintenance_task.cancel()

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
        logger.info("Sandbox pool shut down")

    # ── Public API ────────────────────────────────────────────

    @property
    def available(self) -> bool:
        return self._available

    @property
    def client(self) -> Optional[docker.DockerClient]:
        return self._client

    async def acquire(self, timeout: float = 10.0) -> Optional[str]:
        """Acquire a container ID from the pool. Returns None on timeout."""
        if not self._available or self._client is None:
            return None
        try:
            return await asyncio.wait_for(self._pool.get(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning("Sandbox pool exhausted — no container within %.1fs", timeout)
            return None

    async def release_and_replace(self, container_id: str) -> None:
        """Destroy the used container and create a fresh replacement."""
        self._destroy_container(container_id)
        new_cid = await self._create_container()
        if new_cid:
            await self._pool.put(new_cid)

    # ── Internal ──────────────────────────────────────────────

    def _create_container_sync(self) -> Optional[str]:
        """Synchronous container creation (runs in executor)."""
        if not self._client:
            return None
        try:
            container = self._client.containers.create(
                image=_SANDBOX_IMAGE,
                command=["sleep", "infinity"],
                detach=True,
                network_mode="none",
                mem_limit=f"{settings.SANDBOX_MEMORY_LIMIT_MB}m",
                cpu_period=100_000,
                cpu_quota=100_000 * settings.SANDBOX_CPU_CORES,
                pids_limit=64,
                security_opt=["no-new-privileges"],
                read_only=True,
                tmpfs={"/tmp": f"size={settings.SANDBOX_MEMORY_LIMIT_MB}m"},
                cap_drop=["ALL"],
            )
            return container.id
        except Exception as e:
            logger.error("Failed to create sandbox container: %s", e)
            return None

    async def _create_container(self) -> Optional[str]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._create_container_sync)

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

    async def _maintain_pool(self) -> None:
        """Background task: ensure pool stays at target size."""
        while not self._shutdown:
            try:
                await asyncio.sleep(5)
                current = self._pool.qsize()
                target = settings.SANDBOX_POOL_SIZE
                if current < target and self._client:
                    for _ in range(target - current):
                        cid = await self._create_container()
                        if cid:
                            await self._pool.put(cid)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.debug("Pool maintenance error", exc_info=True)
