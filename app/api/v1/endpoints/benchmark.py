"""Benchmark endpoints."""

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.benchmarks.monotonicity import get_monotonicity_metadata, run_monotonicity_benchmark_stream

router = APIRouter()


@router.get("/monotonicity")
async def get_monotonicity_benchmark():
    """Return static monotonicity benchmark metadata and reference scores."""
    return get_monotonicity_metadata()


@router.post("/monotonicity/run")
async def run_monotonicity_benchmark():
    """
    SSE stream -- evaluate 6 synthetic trajectories and emit scores live.
    """
    async def event_generator():
        async for event in run_monotonicity_benchmark_stream():
            yield event

    return EventSourceResponse(event_generator())
