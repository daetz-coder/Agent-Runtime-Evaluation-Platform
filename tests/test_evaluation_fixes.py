"""Tests for evaluation service fixes."""

from __future__ import annotations

import pytest

from app.services.evaluation_service import EvaluationService


@pytest.mark.asyncio
async def test_finalize_from_parallel_rejects_task_mismatch():
    from app.db.database import async_session_factory
    from app.models.schemas import TaskCreate

    async with async_session_factory() as db:
        service = EvaluationService(db)
        task_a = await service.create_task(TaskCreate(goal="Task A", context={}))
        task_b = await service.create_task(TaskCreate(goal="Task B", context={}))
        evaluation, _ = await service.create_evaluation(task_a.id)
        await db.commit()
        eval_id = evaluation.id

    async with async_session_factory() as db:
        service = EvaluationService(db)
        result = await service.finalize_from_parallel(
            eval_id,
            task_b.id,
            {"planning": {"overall": 80}, "overall": {"overall_score": 80}},
        )
        assert result is None
