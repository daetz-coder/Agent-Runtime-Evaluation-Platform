"""System health helpers."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from app.core.config import settings
from app.db.database import async_session_factory


async def get_system_health() -> dict:
    """Collect health status for core platform and Wiki Agent."""
    db_status = "disconnected"
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    wiki_status = _get_wiki_health()
    overall = "healthy" if db_status == "connected" and wiki_status["milvus"]["available"] else "degraded"
    if db_status == "disconnected":
        overall = "degraded"

    return {
        "status": overall,
        "app": settings.APP_NAME,
        "version": "0.1.0",
        "database": db_status,
        "auth_enabled": settings.AUTH_ENABLED,
        "wiki": wiki_status,
    }


def _get_wiki_health() -> dict:
    """Return Wiki Agent index and knowledge status."""
    from app.wiki_agent.agent.tools.bm25_index import get_bm25_index
    from app.wiki_agent.agent.tools.vector_store import get_vector_store
    from app.wiki_agent.config import settings as wiki_settings

    store = get_vector_store()
    milvus_stats = store.get_stats()
    bm25 = get_bm25_index()
    knowledge_dir = Path(wiki_settings.KNOWLEDGE_DIR)
    page_count = len(list(knowledge_dir.rglob("*.md"))) if knowledge_dir.exists() else 0

    return {
        "knowledge_dir": wiki_settings.KNOWLEDGE_DIR,
        "knowledge_pages": page_count,
        "milvus": milvus_stats,
        "bm25_chunks": len(bm25._tokenized_corpus),
    }
