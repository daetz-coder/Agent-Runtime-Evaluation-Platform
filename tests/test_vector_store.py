"""Tests for Milvus vector store."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.wiki_agent.agent.tools.vector_store import ChunkRecord, MilvusVectorStore


@pytest.fixture
def milvus_db_path(tmp_path: Path) -> str:
    """Provide an isolated Milvus Lite database path."""
    return str(tmp_path / "test_milvus.db")


def test_milvus_vector_store_insert_search_delete(monkeypatch: pytest.MonkeyPatch, milvus_db_path: str) -> None:
    """Vector store should insert, search, and delete chunks by path."""
    monkeypatch.setattr("app.wiki_agent.agent.tools.vector_store.settings.MILVUS_URI", milvus_db_path)

    store = MilvusVectorStore()
    assert store.available

    records = [
        ChunkRecord(
            chunk_id="docs/a.md#chunk0",
            vector=[0.2] * 512,
            path="docs/a.md",
            title="A",
            document="hello milvus",
            tags="test",
            chunk_index=0,
            total_chunks=1,
            updated_at="2025-01-01T00:00:00",
        )
    ]
    store.insert_chunks(records)
    assert store.count() == 1

    hits = store.search([0.2] * 512, limit=1)
    assert hits
    assert hits[0]["path"] == "docs/a.md"
    assert hits[0]["document"] == "hello milvus"

    deleted = store.delete_by_path("docs/a.md")
    assert deleted == 1
    assert store.count() == 0
