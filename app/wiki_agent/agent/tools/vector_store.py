"""Milvus vector store for Wiki Agent semantic search."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.wiki_agent.config import settings

COLLECTION_NAME = settings.MILVUS_COLLECTION
EMBEDDING_DIM = settings.EMBEDDING_DIM


@dataclass
class ChunkRecord:
    """A single wiki knowledge chunk stored in Milvus."""

    chunk_id: str
    vector: list[float]
    path: str
    title: str
    document: str
    tags: str
    chunk_index: int
    total_chunks: int
    updated_at: str


class MilvusVectorStore:
    """Milvus-backed vector index for wiki knowledge chunks."""

    def __init__(self) -> None:
        self._client: Any | None = None
        self._init_error: str | None = None

    @property
    def available(self) -> bool:
        """Return True when Milvus client is ready."""
        return self._get_client() is not None

    def count(self) -> int:
        """Return the number of indexed chunks."""
        client = self._get_client()
        if client is None:
            return 0
        try:
            stats = client.get_collection_stats(COLLECTION_NAME)
            return int(stats.get("row_count", 0))
        except Exception:
            return 0

    def insert_chunks(self, records: list[ChunkRecord]) -> None:
        """Insert wiki chunk records into Milvus."""
        if not records:
            return

        client = self._get_client()
        if client is None:
            raise RuntimeError(self._init_error or "Milvus client unavailable")

        data = [
            {
                "id": record.chunk_id,
                "vector": record.vector,
                "path": record.path,
                "title": record.title,
                "document": record.document,
                "tags": record.tags,
                "chunk_index": record.chunk_index,
                "total_chunks": record.total_chunks,
                "updated_at": record.updated_at,
            }
            for record in records
        ]
        client.insert(collection_name=COLLECTION_NAME, data=data)

    def delete_by_path(self, path: str) -> int:
        """Delete all chunks belonging to a wiki page path."""
        client = self._get_client()
        if client is None:
            return 0

        try:
            existing = client.query(
                collection_name=COLLECTION_NAME,
                filter=_path_filter(path),
                output_fields=["id"],
            )
            if not existing:
                return 0
            client.delete(collection_name=COLLECTION_NAME, filter=_path_filter(path))
            return len(existing)
        except Exception:
            return 0

    def search(self, query_vector: list[float], limit: int) -> list[dict[str, Any]]:
        """Search chunks by vector similarity."""
        client = self._get_client()
        if client is None:
            return []

        try:
            results = client.search(
                collection_name=COLLECTION_NAME,
                data=[query_vector],
                limit=limit,
                output_fields=["path", "title", "document", "tags", "chunk_index"],
            )
        except Exception as exc:
            print(f"[Milvus] Search failed: {exc}")
            return []

        hits: list[dict[str, Any]] = []
        if not results or not results[0]:
            return hits

        for hit in results[0]:
            entity = hit.get("entity", {})
            distance = float(hit.get("distance", 0.0))
            hits.append(
                {
                    "chunk_id": hit.get("id", ""),
                    "path": entity.get("path", ""),
                    "title": entity.get("title", ""),
                    "document": entity.get("document", ""),
                    "score": 1.0 - distance,
                }
            )
        return hits

    def get_stats(self) -> dict[str, Any]:
        """Return Milvus connection and collection statistics."""
        client = self._get_client()
        if client is None:
            return {
                "available": False,
                "uri": settings.MILVUS_URI,
                "collection": COLLECTION_NAME,
                "embedding_dim": EMBEDDING_DIM,
                "total_chunks": 0,
                "unique_pages": 0,
                "error": self._init_error,
            }

        total = self.count()
        paths = self._collect_paths(client)
        return {
            "available": True,
            "uri": settings.MILVUS_URI,
            "collection": COLLECTION_NAME,
            "embedding_dim": EMBEDDING_DIM,
            "total_chunks": total,
            "unique_pages": len(paths),
            "error": None,
        }

    def list_paths(self, limit: int = 500) -> list[dict[str, Any]]:
        """List wiki pages indexed in Milvus with chunk counts."""
        client = self._get_client()
        if client is None:
            return []

        path_counts = self._collect_paths(client)
        items = [{"path": path, "chunk_count": count} for path, count in sorted(path_counts.items())]
        return items[:limit]

    def list_chunks(
        self,
        path: str | None = None,
        keyword: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> dict[str, Any]:
        """List indexed chunks with optional filters and pagination."""
        client = self._get_client()
        if client is None:
            return {"items": [], "total": 0, "offset": offset, "limit": limit}

        filter_expr = _build_list_filter(path, keyword)
        safe_limit = max(1, min(limit, 100))
        safe_offset = max(0, offset)

        try:
            rows = client.query(
                collection_name=COLLECTION_NAME,
                filter=filter_expr,
                output_fields=[
                    "id",
                    "path",
                    "title",
                    "document",
                    "tags",
                    "chunk_index",
                    "total_chunks",
                    "updated_at",
                ],
                limit=safe_limit,
                offset=safe_offset,
            )
        except Exception as exc:
            print(f"[Milvus] Query failed: {exc}")
            return {"items": [], "total": 0, "offset": safe_offset, "limit": safe_limit, "error": str(exc)}

        total = self._count_matching(client, filter_expr)
        items = [_format_chunk_row(row) for row in rows]
        items.sort(key=lambda item: (item["path"], item["chunk_index"]))

        return {
            "items": items,
            "total": total,
            "offset": safe_offset,
            "limit": safe_limit,
        }

    def _collect_paths(self, client: Any) -> dict[str, int]:
        """Aggregate chunk counts grouped by wiki page path."""
        try:
            rows = client.query(
                collection_name=COLLECTION_NAME,
                filter="",
                output_fields=["path"],
                limit=16384,
            )
        except Exception:
            return {}

        counts: dict[str, int] = {}
        for row in rows:
            page_path = row.get("path", "")
            if page_path:
                counts[page_path] = counts.get(page_path, 0) + 1
        return counts

    def _count_matching(self, client: Any, filter_expr: str) -> int:
        """Count rows matching a filter expression."""
        try:
            rows = client.query(
                collection_name=COLLECTION_NAME,
                filter=filter_expr,
                output_fields=["id"],
                limit=16384,
            )
            return len(rows)
        except Exception:
            return 0

    def _get_client(self) -> Any | None:
        if self._client is not None:
            return self._client
        if self._init_error is not None:
            return None

        try:
            from pymilvus import MilvusClient

            uri = settings.MILVUS_URI
            if not uri.startswith("http"):
                Path(uri).parent.mkdir(parents=True, exist_ok=True)

            client = MilvusClient(uri=uri)
            if not client.has_collection(COLLECTION_NAME):
                client.create_collection(
                    collection_name=COLLECTION_NAME,
                    dimension=EMBEDDING_DIM,
                    metric_type="COSINE",
                    id_type="string",
                    max_length=512,
                )
            # Load collection into memory for queries (required for Milvus Lite)
            client.load_collection(COLLECTION_NAME)
            self._client = client
            return self._client
        except Exception as exc:
            self._init_error = str(exc)
            print(f"[Milvus] Initialization failed: {exc}")
            return None


def _path_filter(path: str) -> str:
    """Build a Milvus filter expression for a wiki page path."""
    escaped = path.replace("\\", "\\\\").replace('"', '\\"')
    return f'path == "{escaped}"'


def _build_list_filter(path: str | None, keyword: str | None) -> str:
    """Build a Milvus filter expression for admin listing."""
    parts: list[str] = []
    if path:
        parts.append(_path_filter(path))
    if keyword:
        escaped = keyword.replace("\\", "\\\\").replace('"', '\\"')
        parts.append(f'document like "%{escaped}%"')
    return " and ".join(parts)


def _format_chunk_row(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Milvus query row for API responses."""
    document = row.get("document") or ""
    return {
        "chunk_id": row.get("id", ""),
        "path": row.get("path", ""),
        "title": row.get("title", ""),
        "document": document,
        "document_preview": document[:200],
        "tags": row.get("tags", ""),
        "chunk_index": int(row.get("chunk_index", 0)),
        "total_chunks": int(row.get("total_chunks", 0)),
        "updated_at": row.get("updated_at", ""),
    }


_vector_store: MilvusVectorStore | None = None


def get_vector_store() -> MilvusVectorStore:
    """Return the shared Milvus vector store instance."""
    global _vector_store
    if _vector_store is None:
        _vector_store = MilvusVectorStore()
    return _vector_store
