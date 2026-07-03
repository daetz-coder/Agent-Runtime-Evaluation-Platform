"""Wiki Agent 独立启动入口

用法:
    # 开发模式（热重载）
    python -m app.wiki_agent --reload

    # 生产模式
    python -m app.wiki_agent --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
from typing import AsyncGenerator


def parse_args():
    parser = argparse.ArgumentParser(description="Wiki Agent 独立服务")
    parser.add_argument("--host", default="0.0.0.0", help="绑定地址 (默认 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="端口 (默认 8000)")
    parser.add_argument("--reload", action="store_true", help="开发模式热重载")
    return parser.parse_args()


def create_app(host: str = "0.0.0.0", port: int = 8000):
    """创建 Wiki Agent 独立 FastAPI 应用"""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    from app.wiki_agent.bootstrap import startup
    from app.wiki_agent.database import init_db
    from app.wiki_agent.routers import chat, debug, vector_admin, wiki

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        print("[Wiki Agent] 正在初始化...")
        await init_db()
        await startup()
        print("[Wiki Agent] 启动完成 ✓")
        print(f"[Wiki Agent] 后端: http://{host}:{port}")
        print("[Wiki Agent] 前端: cd frontend && npm run dev → http://localhost:5173")
        yield
        print("[Wiki Agent] 正在关闭...")

    app = FastAPI(
        title="Wiki Agent",
        description="基于 RAG 的个人知识库问答系统",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS — 允许前端跨域
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    app.include_router(chat.router)
    app.include_router(wiki.router)
    app.include_router(debug.router)
    app.include_router(vector_admin.api_router)
    app.include_router(vector_admin.page_router)

    # 健康检查
    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "wiki-agent"}

    return app


def main():
    args = parse_args()

    if args.reload:
        # 开发模式：用 uvicorn 热重载
        import uvicorn
        uvicorn.run(
            "app.wiki_agent.__main__:create_app",
            host=args.host,
            port=args.port,
            reload=True,
            factory=True,
        )
    else:
        # 生产模式：直接运行
        import uvicorn
        app = create_app(host=args.host, port=args.port)
        uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
