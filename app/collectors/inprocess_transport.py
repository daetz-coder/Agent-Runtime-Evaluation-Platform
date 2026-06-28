"""
In-process collector transport — bypass HTTP loopback when embedded in the platform.

Wiki Agent runs inside the same FastAPI/uvicorn process. Sync HTTP calls to
127.0.0.1:8000 while handling a chat request block the event loop and cause
trajectory/task PUT timeouts (self-deadlock).

This module writes directly via EvaluationService + async SQLAlchemy.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


async def create_task_record(
    task_id: str,
    goal: str,
    context: Optional[Dict[str, Any]] = None,
) -> str:
    """Create task row without HTTP."""
    from app.db.database import async_session_factory
    from app.models.schemas import TaskCreate
    from app.services.evaluation_service import EvaluationService

    async with async_session_factory() as db:
        service = EvaluationService(db)
        task = await service.create_task(
            TaskCreate(id=task_id, goal=goal, context=context),
            workspace_id=None,
        )
        await db.commit()
        return task.id


async def persist_collector_session(
    task_id: str,
    steps: List[Dict[str, Any]],
    *,
    auto_run: bool = False,
) -> None:
    """Flush buffered trajectory, mark task completed, optionally queue evaluation."""
    from app.db.database import async_session_factory
    from app.models.schemas import TaskUpdate
    from app.services.evaluation_service import EvaluationService

    eval_id: Optional[str] = None

    async with async_session_factory() as db:
        service = EvaluationService(db)
        if steps:
            await service.add_trajectory(task_id, steps, workspace_id=None)
        await service.update_task(task_id, TaskUpdate(status="completed"), workspace_id=None)
        if auto_run:
            evaluation = await service.create_evaluation(task_id, workspace_id=None)
            eval_id = evaluation.id if evaluation else None
        await db.commit()

    if auto_run and eval_id:
        asyncio.create_task(_run_evaluation_background(task_id, eval_id))


async def _run_evaluation_background(task_id: str, eval_id: str) -> None:
    """Run evaluation graph without blocking the chat response."""
    from app.db.database import async_session_factory
    from app.services.evaluation_service import EvaluationService

    try:
        async with async_session_factory() as db:
            service = EvaluationService(db)
            result = await service.run_evaluation(task_id=task_id, workspace_id=None)
            await db.commit()
            if result is None:
                await service.abort_pending_evaluation(eval_id, task_id, workspace_id=None)
                await db.commit()
    except Exception as exc:
        logger.error("In-process evaluation failed for task %s: %s", task_id, exc)
        try:
            async with async_session_factory() as db:
                service = EvaluationService(db)
                await service.abort_pending_evaluation(eval_id, task_id, workspace_id=None)
                await db.commit()
        except Exception as cleanup_exc:
            logger.error("Failed to abort evaluation %s: %s", eval_id, cleanup_exc)
