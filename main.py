"""Wiki Agent 独立运行入口。

不依赖评估平台的数据库、评估引擎、Agent Runtime 等组件。
仅启动 Wiki Agent 的 API 和前端。

Usage:
    python main.py                    # 默认端口 8000
    WIKI_PORT=8080 python main.py     # 自定义端口
"""

from __future__ import annotations

import os
import warnings

warnings.filterwarnings("ignore", message=".*allowed_objects.*")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="langgraph")

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Wiki Agent 独立模式生命周期。"""
    print("[Wiki Agent] Starting standalone mode...")

    from app.wiki_agent.bootstrap import startup
    await startup()

    print("[Wiki Agent] Ready!")
    print("[Wiki Agent] API Docs: http://localhost:{}/docs".format(os.environ.get("WIKI_PORT", "8000")))

    yield

    print("[Wiki Agent] Shutting down...")


def create_app() -> FastAPI:
    """创建 Wiki Agent 独立应用。"""
    app = FastAPI(
        title="Wiki Agent",
        description="个人知识库问答系统 — 独立运行模式",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── 注册 Wiki Agent 路由 ──

    from app.wiki_agent.routers import chat as wiki_chat
    from app.wiki_agent.routers import debug as wiki_debug
    from app.wiki_agent.routers import vector_admin as wiki_vector_api
    from app.wiki_agent.routers import wiki as wiki_router

    app.include_router(wiki_router.router)
    app.include_router(wiki_chat.router)
    app.include_router(wiki_vector_api.api_router)
    app.include_router(wiki_vector_api.page_router)
    app.include_router(wiki_debug.router)

    # ── 前端静态文件 ──

    frontend_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
    if os.path.isdir(frontend_dist):
        app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

        @app.get("/", include_in_schema=False)
        async def serve_index():
            from pathlib import Path
            index_path = Path(frontend_dist) / "index.html"
            return HTMLResponse(content=index_path.read_text(encoding="utf-8"))

        # SPA 路由回退：所有未匹配的路径都返回 index.html
        @app.get("/{path:path}", include_in_schema=False)
        async def spa_fallback(path: str):
            # 排除 API 路径和静态资源
            if path.startswith(("api/", "docs", "redoc", "health", "assets/")):
                from fastapi import HTTPException
                raise HTTPException(status_code=404, detail="Not found")
            from pathlib import Path
            index_path = Path(frontend_dist) / "index.html"
            return HTMLResponse(content=index_path.read_text(encoding="utf-8"))

        print(f"[Wiki Agent] Frontend served from {frontend_dist}")
    else:
        print(f"[Wiki Agent] Frontend not found at {frontend_dist} — API only mode")

    # ── 健康检查 ──

    @app.get("/health")
    async def health():
        from app.wiki_agent.agent.tools.vector_store import get_vector_store
        from app.wiki_agent.agent.tools.bm25_index import get_bm25_index

        store = get_vector_store()
        bm25 = get_bm25_index()

        return {
            "status": "ok",
            "mode": "standalone",
            "milvus": {"available": store.available, "chunks": store.count()},
            "bm25": {"chunks": len(bm25._tokenized_corpus)},
        }

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("WIKI_PORT", "8000"))
    host = os.environ.get("WIKI_HOST", "0.0.0.0")
    print(f"[Wiki Agent] Starting on http://{host}:{port}")
    uvicorn.run("main:app", host=host, port=port, reload=True)
