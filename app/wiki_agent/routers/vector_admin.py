"""Milvus vector admin API and web UI."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from app.wiki_agent.agent.tools.vector_store import get_vector_store
from app.wiki_agent.wiki.vector_schemas import (
    VectorChunkListResponse,
    VectorPathListResponse,
    VectorStatsResponse,
)

api_router = APIRouter(prefix="/api/wiki", tags=["wiki-vector"])
page_router = APIRouter(tags=["wiki-vector"])

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@api_router.get("/vector-stats", response_model=VectorStatsResponse)
def get_vector_stats() -> VectorStatsResponse:
    """Return Milvus connection status and collection statistics."""
    stats = get_vector_store().get_stats()
    return VectorStatsResponse(**stats)


@api_router.get("/vector-paths", response_model=VectorPathListResponse)
def list_vector_paths(limit: int = Query(default=500, ge=1, le=2000)) -> VectorPathListResponse:
    """List wiki page paths indexed in Milvus."""
    items = get_vector_store().list_paths(limit=limit)
    return VectorPathListResponse(items=items, total=len(items))


@api_router.get("/vector-chunks", response_model=VectorChunkListResponse)
def list_vector_chunks(
    path: str | None = Query(default=None, description="Filter by exact wiki page path"),
    keyword: str | None = Query(default=None, description="Filter by document keyword"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> VectorChunkListResponse:
    """List Milvus chunks with optional filters and pagination."""
    result = get_vector_store().list_chunks(path=path, keyword=keyword, offset=offset, limit=limit)
    return VectorChunkListResponse(**result)


@page_router.get("/wiki-admin", response_class=HTMLResponse, include_in_schema=False)
def vector_admin_page() -> HTMLResponse:
    """Serve the Milvus vector admin web UI."""
    html_path = _STATIC_DIR / "vector_admin.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
