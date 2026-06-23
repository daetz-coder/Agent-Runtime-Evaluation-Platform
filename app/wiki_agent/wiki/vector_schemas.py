"""Pydantic schemas for Milvus vector admin APIs."""

from __future__ import annotations

from pydantic import BaseModel, Field


class VectorStatsResponse(BaseModel):
    """Milvus collection statistics."""

    available: bool
    uri: str
    collection: str
    embedding_dim: int
    total_chunks: int
    unique_pages: int
    error: str | None = None


class VectorPathItem(BaseModel):
    """A wiki page path with its chunk count in Milvus."""

    path: str
    chunk_count: int


class VectorChunkItem(BaseModel):
    """A single indexed chunk stored in Milvus."""

    chunk_id: str
    path: str
    title: str
    document: str
    document_preview: str
    tags: str
    chunk_index: int
    total_chunks: int
    updated_at: str


class VectorChunkListResponse(BaseModel):
    """Paginated Milvus chunk listing."""

    items: list[VectorChunkItem]
    total: int
    offset: int
    limit: int
    error: str | None = None


class VectorPathListResponse(BaseModel):
    """Wiki paths indexed in Milvus."""

    items: list[VectorPathItem]
    total: int = Field(description="Number of paths returned")
