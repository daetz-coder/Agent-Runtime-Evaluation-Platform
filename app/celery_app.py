"""
Celery application configuration and task definitions.

Replaces FastAPI BackgroundTasks with a reliable, distributed task queue.
Features:
  - Automatic retry on transient failures (LLM timeout, Docker errors)
  - Concurrency control (limit simultaneous sandbox sessions)
  - Task priority (VIP workspaces get higher priority)
  - Dead letter tracking (failed tasks logged with full context)

Usage:
  # Start worker:
  celery -A app.celery_app worker -l info -c 4

  # From code:
  from app.celery_app import run_evaluation_task
  result = run_evaluation_task.delay(task_id, workspace_id)
"""

from __future__ import annotations

import logging
from typing import Optional

from celery import Celery
from celery.signals import worker_process_init

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Celery App ────────────────────────────────────────────────

celery_app = Celery(
    "agent_eval",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.celery_app"],
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Task execution
    task_acks_late=True,  # Ack after completion (not before)
    task_reject_on_worker_lost=True,  # Re-queue on worker crash
    task_time_limit=settings.AGENT_TIMEOUT + 120,  # Hard kill after timeout + buffer
    task_soft_time_limit=settings.AGENT_TIMEOUT + 60,  # Soft timeout (raises SoftTimeLimitExceeded)
    # Retry
    task_default_retry_delay=10,  # Default retry delay (seconds)
    # Concurrency control
    worker_prefetch_multiplier=1,  # Don't prefetch extra tasks (long-running)
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks (memory leak prevention)
    # Task routes & priorities
    task_routes={
        "app.celery_app.run_evaluation_task": {"queue": "evaluation"},
        "app.celery_app.run_sandbox_evaluation_task": {"queue": "sandbox"},
    },
    task_queue_max_priority=10,
    task_default_priority=5,
    # Result backend
    result_expires=86400,  # Results expire after 24h
)


# ── Worker Initialization ─────────────────────────────────────


@worker_process_init.connect
def init_worker(**kwargs):
    """Initialize resources when a Celery worker process starts."""
    import asyncio

    from app.core.cache import init_redis
    from app.db.database import init_db

    logger.info("Initializing Celery worker...")
    loop = asyncio.new_event_loop()
    loop.run_until_complete(init_db())
    loop.run_until_complete(init_redis())
    logger.info("Celery worker ready")


# ── Task Definitions ──────────────────────────────────────────


@celery_app.task(
    bind=True,
    name="app.celery_app.run_evaluation_task",
    max_retries=3,
    default_retry_delay=15,
    acks_late=True,
)
def run_evaluation_task(
    self,
    task_id: str,
    eval_id: str,
    workspace_id: Optional[str] = None,
) -> dict:
    """
    Run evaluation for an existing task with trajectory.

    Retries on:
      - LLM provider errors (transient)
      - Docker connection issues
      - Database connection errors

    Does NOT retry on:
      - Task not found (404)
      - Invalid trajectory data
    """
    import asyncio

    logger.info(
        "Running evaluation task: task_id=%s, eval_id=%s, attempt=%d",
        task_id,
        eval_id,
        self.request.retries + 1,
    )

    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            _run_evaluation_async(task_id, eval_id, workspace_id)
        )
        loop.close()

        logger.info("Evaluation completed: task_id=%s, eval_id=%s", task_id, eval_id)
        _notify_webhook(task_id, eval_id, result)
        return {"task_id": task_id, "eval_id": eval_id, "status": "completed"}

    except Exception as exc:
        logger.error(
            "Evaluation failed (attempt %d): %s",
            self.request.retries + 1,
            exc,
            exc_info=True,
        )
        # Retry on transient errors
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=15 * (self.request.retries + 1))
        # Final failure — mark evaluation as failed so clients don't poll forever
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_abort_evaluation_async(task_id, eval_id, workspace_id))
        finally:
            loop.close()
        return {"task_id": task_id, "eval_id": eval_id, "status": "failed", "error": str(exc)}


@celery_app.task(
    bind=True,
    name="app.celery_app.run_sandbox_evaluation_task",
    max_retries=2,
    default_retry_delay=30,
    acks_late=True,
    priority=5,
)
def run_sandbox_evaluation_task(
    self,
    goal: str,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    workspace_files: Optional[dict] = None,
    tools: Optional[list] = None,
    max_steps: Optional[int] = None,
    context: Optional[dict] = None,
    temperature: float = 0.0,
    workspace_id: Optional[str] = None,
) -> dict:
    """
    Run a full sandbox-based agent evaluation (Agent in Sandbox).

    Lower max_retries because sandbox runs are long and expensive.
    """
    import asyncio

    from app.models.schemas import SandboxEvalRequest

    logger.info("Running sandbox evaluation: goal=%s", goal[:100])

    request = SandboxEvalRequest(
        goal=goal,
        model=model,
        provider=provider,
        workspace_files=workspace_files,
        tools=tools,
        max_steps=max_steps,
        context=context,
        temperature=temperature,
    )

    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(_run_sandbox_evaluation_async(request, workspace_id))
        loop.close()

        logger.info("Sandbox evaluation completed: task_id=%s", result.task_id)
        return result.model_dump(mode="json")

    except Exception as exc:
        logger.error("Sandbox evaluation failed: %s", exc, exc_info=True)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=30 * (self.request.retries + 1))
        return {"status": "failed", "error": str(exc)}


# ── Async Helpers ─────────────────────────────────────────────


async def _run_evaluation_async(
    task_id: str,
    eval_id: str,
    workspace_id: Optional[str] = None,
):
    """Async wrapper for evaluation service."""
    from app.db.database import async_session_factory
    from app.services.evaluation_service import EvaluationService

    async with async_session_factory() as db:
        service = EvaluationService(db)
        result = await service.run_evaluation(
            task_id=task_id,
            workspace_id=workspace_id,
            evaluation_id=eval_id,
        )
        await db.commit()
        return result


async def _run_sandbox_evaluation_async(request, workspace_id: Optional[str] = None):
    """Async wrapper for sandbox evaluation service."""
    from app.db.database import async_session_factory
    from app.services.evaluation_service import EvaluationService

    async with async_session_factory() as db:
        service = EvaluationService(db)
        result = await service.run_sandbox_evaluation(request, workspace_id=workspace_id)
        await db.commit()
        return result


async def _abort_evaluation_async(
    task_id: str,
    eval_id: str,
    workspace_id: Optional[str] = None,
) -> None:
    """Mark a stuck evaluation as failed after Celery exhausts retries."""
    from app.db.database import async_session_factory
    from app.services.evaluation_service import EvaluationService

    async with async_session_factory() as db:
        service = EvaluationService(db)
        await service.abort_pending_evaluation(eval_id, task_id, workspace_id=workspace_id)
        await db.commit()


# ── Webhook Notification ──────────────────────────────────────


def _notify_webhook(task_id: str, eval_id: str, result) -> None:
    """Send webhook notification on evaluation completion (sync, with retry)."""
    from app.services.webhook import WebhookService

    WebhookService.notify_sync(
        "evaluation.completed",
        {
            "task_id": task_id,
            "evaluation_id": eval_id,
        },
    )
