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


@pytest.mark.asyncio
async def test_create_task_cross_workspace_conflict():
    from app.api.workspace import Workspace
    from app.db.database import async_session_factory
    from app.models.schemas import TaskCreate

    async with async_session_factory() as db:
        ws_a = Workspace(id="ws-a-test", name="WS A", api_key="key_a_test")
        ws_b = Workspace(id="ws-b-test", name="WS B", api_key="key_b_test")
        db.add_all([ws_a, ws_b])
        await db.flush()

        service = EvaluationService(db)
        task = await service.create_task(
            TaskCreate(id="shared-task-id", goal="Shared", context={}),
            workspace_id="ws-a-test",
        )
        await db.commit()
        assert task.id == "shared-task-id"

        with pytest.raises(ValueError, match="different workspace scope"):
            await service.create_task(
                TaskCreate(id="shared-task-id", goal="Shared again", context={}),
                workspace_id="ws-b-test",
            )
