"""Collector session isolation tests."""

import asyncio

import pytest

from sdk.collector import get_collector, reset_collector


@pytest.mark.asyncio
async def test_collector_sessions_isolated_by_asyncio_task():
    """Concurrent collector.start() calls must not overwrite each other's task_id."""
    reset_collector()
    collector = get_collector()
    collector._enabled = False  # local-only, no HTTP

    async def run_session(label: str) -> str:
        task_id = collector.start(f"goal-{label}", {"label": label})
        await asyncio.sleep(0.05)
        return task_id

    id_a, id_b, id_c = await asyncio.gather(
        run_session("a"),
        run_session("b"),
        run_session("c"),
    )
    assert len({id_a, id_b, id_c}) == 3
