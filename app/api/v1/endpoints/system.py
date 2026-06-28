"""System endpoints."""

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.services.system_health import get_system_health

router = APIRouter()


@router.get("/health")
async def get_health():
    """Return platform health status including database and Wiki Agent index."""
    return await get_system_health()


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    """Prometheus metrics endpoint."""
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

    return PlainTextResponse(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
