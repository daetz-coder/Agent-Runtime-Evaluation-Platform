"""Workspace quota enforcement tests."""

import pytest

from app.api.workspace import Workspace
from app.services.quota import QuotaExceeded, QuotaService


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
