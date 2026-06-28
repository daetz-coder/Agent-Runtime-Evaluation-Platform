"""Workspace quota enforcement tests."""

import pytest

from app.api.workspace import Workspace
from app.db.models import AgentTask, TaskStatus
from app.services.quota import SANDBOX_EVAL_MODE, QuotaExceeded, QuotaService


@pytest.mark.asyncio
async def test_check_max_steps_exceeded():
    from app.db.database import async_session_factory

    async with async_session_factory() as db:
        ws = Workspace(
            id="ws-quota-steps",
            name="Quota Steps WS",
            api_key="ws_key_steps_test",
            max_steps_per_eval=10,
        )
        db.add(ws)
        await db.flush()

        quota = QuotaService(db)
        with pytest.raises(QuotaExceeded) as exc:
            await quota.check_max_steps(ws.id, 25)
        assert exc.value.quota_type == "max_steps_per_eval"


@pytest.mark.asyncio
async def test_sandbox_quota_counts_only_sandbox_tasks():
    from app.db.database import async_session_factory

    async with async_session_factory() as db:
        ws = Workspace(
            id="ws-quota-sandbox",
            name="Quota Sandbox WS",
            api_key="ws_key_sandbox_test",
            sandbox_quota=1,
        )
        db.add(ws)
        await db.flush()

        legacy_task = AgentTask(
            id="task-legacy-running",
            workspace_id=ws.id,
            goal="legacy eval",
            context={"source": "external"},
            status=TaskStatus.RUNNING,
        )
        sandbox_task = AgentTask(
            id="task-sandbox-running",
            workspace_id=ws.id,
            goal="sandbox eval",
            context={"eval_mode": SANDBOX_EVAL_MODE},
            status=TaskStatus.RUNNING,
        )
        db.add_all([legacy_task, sandbox_task])
        await db.flush()

        quota = QuotaService(db)
        with pytest.raises(QuotaExceeded):
            await quota.check_sandbox_quota(ws.id)
