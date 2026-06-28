"""Benchmark endpoints."""

from fastapi import APIRouter, Depends

from app.api.workspace import WorkspaceRole
from app.api.workspace_context import WorkspaceContext, get_workspace_context, require_role
from app.benchmarks.monotonicity import get_monotonicity_metadata, run_monotonicity_benchmark_stream
from sse_starlette.sse import EventSourceResponse

router = APIRouter()


@router.get("/monotonicity")
async def get_monotonicity_benchmark():
    """Return static monotonicity benchmark metadata and reference scores."""
    return get_monotonicity_metadata()


@router.post("/monotonicity/run")
async def run_monotonicity_benchmark(
    ctx: WorkspaceContext = Depends(get_workspace_context),
):
    """
    SSE stream — evaluate 6 synthetic trajectories and emit scores live.

    Requires EVALUATOR role when AUTH_ENABLED=true.
    """
    require_role(ctx, WorkspaceRole.EVALUATOR)

    async def event_generator():
        async for event in run_monotonicity_benchmark_stream():
            yield event

    return EventSourceResponse(event_generator())
