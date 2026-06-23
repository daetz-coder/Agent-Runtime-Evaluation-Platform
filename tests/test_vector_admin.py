"""Tests for Milvus vector admin API."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.wiki_agent.agent.tools.vector_store import ChunkRecord, MilvusVectorStore


@pytest.fixture
def milvus_db_path(tmp_path: Path) -> str:
    """Provide an isolated Milvus Lite database path."""
    return str(tmp_path / "admin_milvus.db")


@pytest.fixture
async def client(monkeypatch: pytest.MonkeyPatch, milvus_db_path: str):
    """HTTP client with isolated Milvus storage."""
    monkeypatch.setattr("app.wiki_agent.agent.tools.vector_store.settings.MILVUS_URI", milvus_db_path)
    monkeypatch.setattr("app.wiki_agent.agent.tools.vector_store._vector_store", None)

    store = MilvusVectorStore()
    store.insert_chunks(
        [
            ChunkRecord(
                chunk_id="docs/a.md#chunk0",
                vector=[0.2] * 512,
                path="docs/a.md",
                title="Page A",
                document="hello milvus admin",
                tags="test",
                chunk_index=0,
                total_chunks=1,
                updated_at="2025-01-01T00:00:00",
            ),
            ChunkRecord(
                chunk_id="docs/b.md#chunk0",
                vector=[0.3] * 512,
                path="docs/b.md",
                title="Page B",
                document="another chunk",
                tags="demo",
                chunk_index=0,
                total_chunks=1,
                updated_at="2025-01-02T00:00:00",
            ),
        ]
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


@pytest.mark.asyncio
async def test_vector_stats(client: AsyncClient) -> None:
    """Stats endpoint should report Milvus collection summary."""
    response = await client.get("/api/wiki/vector-stats")
    assert response.status_code == 200
    data = response.json()
    assert data["available"] is True
    assert data["total_chunks"] == 2
    assert data["unique_pages"] == 2
    assert data["embedding_dim"] == 512


@pytest.mark.asyncio
async def test_vector_paths(client: AsyncClient) -> None:
    """Paths endpoint should list indexed wiki pages."""
    response = await client.get("/api/wiki/vector-paths")
    assert response.status_code == 200
    data = response.json()
    paths = {item["path"] for item in data["items"]}
    assert paths == {"docs/a.md", "docs/b.md"}


@pytest.mark.asyncio
async def test_vector_chunks_filter_and_pagination(client: AsyncClient) -> None:
    """Chunks endpoint should support path filter and pagination."""
    response = await client.get("/api/wiki/vector-chunks", params={"path": "docs/a.md", "limit": 10})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["path"] == "docs/a.md"
    assert "hello milvus" in data["items"][0]["document_preview"]


@pytest.mark.asyncio
async def test_vector_admin_page(client: AsyncClient) -> None:
    """Admin page should be served as HTML."""
    response = await client.get("/wiki-admin")
    assert response.status_code == 200
    assert "Milvus 向量管理" in response.text
    assert "/api/wiki/vector-stats" in response.text
