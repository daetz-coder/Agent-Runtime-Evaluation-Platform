"""Wiki Agent 独立后端入口

唯一源码在 app/wiki_agent/（平台包）。
本文件仅做启动配置，通过 import 平台包实现零重复。
"""

import sys
import warnings
from contextlib import asynccontextmanager
from pathlib import Path

# 将项目根目录加入 sys.path，使 app.wiki_agent 可导入
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# 抑制 LangChain/LangGraph 弃用警告
warnings.filterwarnings("ignore", message=".*allowed_objects.*")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="langgraph")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 从平台包导入（唯一源码）
from app.wiki_agent.config import settings
from app.wiki_agent.database import init_db
from app.wiki_agent.routers import wiki, chat, debug


def _sync_indexes_if_needed():
    """检查并自动同步 ChromaDB 和 BM25 索引"""
    from app.wiki_agent.agent.tools.sync_manager import sync_manager
    from app.wiki_agent.agent.tools.bm25_index import get_bm25_index

    collection = sync_manager.chroma_collection
    chroma_ok = collection is not None and collection.count() > 0

    bm25 = get_bm25_index()
    bm25_ok = len(bm25._tokenized_corpus) > 0

    if chroma_ok and bm25_ok:
        print(f"[启动] ChromaDB 已有 {collection.count()} 条记录，BM25 已有 {len(bm25._tokenized_corpus)} 个 chunks，跳过同步")
        return

    print("[启动] 索引不完整，开始自动同步知识库...")

    from app.wiki_agent.wiki import service

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
    except Exception as e:
        print(f"[启动] 获取知识库失败: {e}")
        return

    if not paths:
        print("[启动] 知识库为空，跳过同步")
        return

    from app.wiki_agent.agent.tools.chunker import chunk_markdown
    from datetime import datetime

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

            if not chroma_ok and collection is not None:
                chunk_ids = []
                embeddings = []
                documents = []
                metadatas = []

                for i, chunk in enumerate(chunks):
                    chunk_id = f"{path}#chunk{i}"
                    chunk_ids.append(chunk_id)
                    embedding = sync_manager._generate_embedding(f"{title}\n{chunk}")
                    embeddings.append(embedding)
                    documents.append(chunk)
                    metadatas.append({
                        "path": path,
                        "title": title,
                        "tags": ", ".join(tags),
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "updated_at": datetime.now().isoformat(),
                    })

                collection.add(
                    ids=chunk_ids,
                    embeddings=embeddings,
                    documents=documents,
                    metadatas=metadatas,
                )

            if not bm25_ok:
                bm25.add_document(path, title, chunks)

            success += 1
        except Exception as e:
            print(f"[启动] 同步失败 {path}: {e}")

    if not bm25_ok:
        bm25.save()

    print(f"[启动] 索引同步完成: {success}/{len(paths)} 条")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    await init_db()
    _sync_indexes_if_needed()
    yield


app = FastAPI(title="Wiki Agent", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载路由
app.include_router(wiki.router)
app.include_router(chat.router)
app.include_router(debug.router)

# 确保 knowledge 目录存在
knowledge_dir = Path(settings.KNOWLEDGE_DIR)
knowledge_dir.mkdir(parents=True, exist_ok=True)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.1.0"}
