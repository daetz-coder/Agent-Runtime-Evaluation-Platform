"""Wiki Agent startup helpers for the unified platform."""

from __future__ import annotations

import warnings
from datetime import datetime
from pathlib import Path

warnings.filterwarnings("ignore", message=".*allowed_objects.*")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="langgraph")
warnings.filterwarnings("ignore", message=".*InsecureKeyLength.*")  # ZhipuAI GLM jwt key length

from app.wiki_agent.config import settings

SEED_KNOWLEDGE_DIR = Path(__file__).resolve().parent / "seed" / "knowledge"


def ensure_directories() -> None:
    """Create wiki-agent runtime directories if missing."""
    Path(settings.KNOWLEDGE_DIR).mkdir(parents=True, exist_ok=True)
    if not settings.MILVUS_URI.startswith("http"):
        Path(settings.MILVUS_URI).parent.mkdir(parents=True, exist_ok=True)
    Path(settings.DB_PATH).parent.mkdir(parents=True, exist_ok=True)


def seed_knowledge_if_empty() -> None:
    """Copy bundled sample pages when the knowledge base is empty."""
    knowledge_dir = Path(settings.KNOWLEDGE_DIR)
    if any(knowledge_dir.rglob("*.md")):
        return
    if not SEED_KNOWLEDGE_DIR.exists():
        return

    import shutil

    for src in SEED_KNOWLEDGE_DIR.rglob("*.md"):
        rel = src.relative_to(SEED_KNOWLEDGE_DIR)
        dest = knowledge_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    print(f"[Wiki Agent] Seeded sample knowledge from {SEED_KNOWLEDGE_DIR}")


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
        print(f"[Wiki Agent] Milvus: {store.count()} records, BM25: {len(bm25._tokenized_corpus)} chunks — skip sync")
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
    seed_knowledge_if_empty()
    await init_db()
    sync_indexes_if_needed()
    preload_reranker_if_enabled()
    start_env_monitor()


def start_env_monitor() -> None:
    """启动环境监控器，自动感知 knowledge/ 目录变化"""
    import asyncio

    from app.wiki_agent.agent.tools.env_monitor import get_env_monitor

    monitor = get_env_monitor()
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(monitor.start())
        print("[Wiki Agent] Environment monitor started (poll interval: 5s)")
    except RuntimeError:
        print("[Wiki Agent] Environment monitor skipped (no event loop)")


def preload_reranker_if_enabled() -> None:
    """Eager-load reranker at startup so load errors surface in logs early."""
    if not settings.RERANK_ENABLED:
        print("[Wiki Agent] Rerank disabled (RERANK_ENABLED=false)")
        return

    from app.wiki_agent.agent.tools.reranker import get_reranker_model, get_reranker_status

    get_reranker_model()
    status = get_reranker_status()
    if status["loaded"]:
        print(f"[Wiki Agent] Rerank ready: {status['model_id']}")
    elif status.get("error"):
        print(f"[Wiki Agent] Rerank unavailable: {status['error']}")
    else:
        print("[Wiki Agent] Rerank not loaded")
