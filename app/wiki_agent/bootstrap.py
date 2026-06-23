"""Wiki Agent startup helpers for the unified platform."""

from __future__ import annotations

import warnings
from datetime import datetime
from pathlib import Path

warnings.filterwarnings("ignore", message=".*allowed_objects.*")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="langgraph")
warnings.filterwarnings("ignore", message=".*InsecureKeyLength.*")  # ZhipuAI GLM jwt key length

from app.wiki_agent.config import settings


def ensure_directories() -> None:
    """Create wiki-agent runtime directories if missing."""
    Path(settings.KNOWLEDGE_DIR).mkdir(parents=True, exist_ok=True)
    if not settings.MILVUS_URI.startswith("http"):
        Path(settings.MILVUS_URI).parent.mkdir(parents=True, exist_ok=True)
    Path(settings.DB_PATH).parent.mkdir(parents=True, exist_ok=True)


def sync_indexes_if_needed() -> None:
    """Sync Milvus and BM25 indexes on first startup or when data is empty."""
    from app.wiki_agent.agent.tools.bm25_index import get_bm25_index
    from app.wiki_agent.agent.tools.sync_manager import sync_manager
    from app.wiki_agent.agent.tools.vector_store import ChunkRecord
    from app.wiki_agent.wiki import service

    store = sync_manager.vector_store
    milvus_ok = store.available and store.count() > 0

    bm25 = get_bm25_index()
    bm25_ok = len(bm25._tokenized_corpus) > 0

    if milvus_ok and bm25_ok:
        print(
            f"[Wiki Agent] Milvus: {store.count()} records, "
            f"BM25: {len(bm25._tokenized_corpus)} chunks — skip sync"
        )
        return

    print("[Wiki Agent] Indexes incomplete, syncing knowledge base...")

    def collect_pages(node):
        result = []
        if not node.is_dir:
            result.append(node.path)
        if node.children:
            for child in node.children:
                result.extend(collect_pages(child))
        return result

    try:
        tree = service.get_tree()
        paths = collect_pages(tree)
    except Exception as exc:
        print(f"[Wiki Agent] Failed to load knowledge tree: {exc}")
        return

    if not paths:
        print("[Wiki Agent] Knowledge base is empty, skip sync")
        return

    from app.wiki_agent.agent.tools.chunker import chunk_markdown

    success = 0
    for path in paths:
        try:
            page = service.get_page(path)
            content = page.content
            title = page.title
            tags = page.tags or []

            chunks = chunk_markdown(content, chunk_size=500, chunk_overlap=50)
            if not chunks:
                chunks = [content]

            if not milvus_ok and store.available:
                updated_at = datetime.now().isoformat()
                records: list[ChunkRecord] = []
                for i, chunk in enumerate(chunks):
                    records.append(
                        ChunkRecord(
                            chunk_id=f"{path}#chunk{i}",
                            vector=sync_manager._generate_embedding(f"{title}\n{chunk}"),
                            path=path,
                            title=title,
                            document=chunk,
                            tags=", ".join(tags),
                            chunk_index=i,
                            total_chunks=len(chunks),
                            updated_at=updated_at,
                        )
                    )
                store.insert_chunks(records)

            if not bm25_ok:
                bm25.add_document(path, title, chunks)

            success += 1
        except Exception as exc:
            print(f"[Wiki Agent] Sync failed for {path}: {exc}")

    if not bm25_ok:
        bm25.save()

    print(
        f"[Wiki Agent] Index sync done: {success}/{len(paths)} "
        f"(Milvus: {'skip' if milvus_ok else 'synced'}, "
        f"BM25: {'skip' if bm25_ok else 'synced'})"
    )


async def startup() -> None:
    """Initialize wiki-agent resources during platform startup."""
    from app.wiki_agent.database import init_db

    ensure_directories()
    await init_db()
    sync_indexes_if_needed()
