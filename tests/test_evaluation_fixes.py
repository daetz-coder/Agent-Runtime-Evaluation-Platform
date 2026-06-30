"""Tests for evaluation service fixes."""

from __future__ import annotations

import uuid

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


@pytest.mark.asyncio
async def test_create_task_cross_workspace_conflict():
    from app.api.workspace import Workspace
    from app.db.database import async_session_factory
    from app.models.schemas import TaskCreate

    # Use unique IDs to avoid collisions with stale data from previous runs
    suffix = uuid.uuid4().hex[:8]
    ws_a_id = f"ws-a-{suffix}"
    ws_b_id = f"ws-b-{suffix}"
    task_id = f"shared-task-{suffix}"

    async with async_session_factory() as db:
        ws_a = Workspace(id=ws_a_id, name="WS A", api_key=f"key_a_{suffix}")
        ws_b = Workspace(id=ws_b_id, name="WS B", api_key=f"key_b_{suffix}")
        db.add_all([ws_a, ws_b])
        await db.flush()

        service = EvaluationService(db)
        task = await service.create_task(
            TaskCreate(id=task_id, goal="Shared", context={}),
            workspace_id=ws_a_id,
        )
        await db.commit()
        assert task.id == task_id

        with pytest.raises(ValueError, match="different workspace scope"):
            await service.create_task(
                TaskCreate(id=task_id, goal="Shared again", context={}),
                workspace_id=ws_b_id,
            )
