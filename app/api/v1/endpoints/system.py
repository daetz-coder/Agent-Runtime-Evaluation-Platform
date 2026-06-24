"""System endpoints."""

from fastapi import APIRouter

from app.services.system_health import get_system_health

router = APIRouter()


@router.get("/health")
async def get_health():
    """Return platform health status including database and Wiki Agent index."""
    return await get_system_health()
