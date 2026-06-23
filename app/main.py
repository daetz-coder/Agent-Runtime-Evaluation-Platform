"""
FastAPI application entry point.

Agent Runtime Evaluation Platform
- Evaluate Planning, Tool Use, Memory, and Replanning
- Built with LangGraph, FastAPI, and Python
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from app.core.config import settings
from app.db.database import init_db, close_db
from app.api.v1.endpoints import benchmark, evaluation, reports, tasks
from app.wiki_agent.bootstrap import startup as wiki_agent_startup
from app.wiki_agent.routers import chat as wiki_chat
from app.wiki_agent.routers import wiki as wiki_router
from app.api.workspace_endpoints import router as workspace_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    logger.info("Starting %s...", settings.APP_NAME)
    await init_db()
    logger.info("Database initialized")
    logger.info("Starting Wiki Agent...")
    await wiki_agent_startup()
    logger.info("Wiki Agent initialized")
    yield
    logger.info("Shutting down...")
    await close_db()
    logger.info("Database connections closed")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        description="""
## Agent Runtime Evaluation Platform

Evaluate the runtime quality of AI agents across 6 dimensions:

1. **Planning Quality** - Coverage, ordering, granularity, completeness
2. **Tactical Decisions** - Relevance, efficiency, correctness of next actions
3. **Tool Use** - Selection quality, parameter accuracy, result utilization
4. **Memory** - Retention, relevance, consistency of recalled information
5. **Replanning** - Trigger appropriateness, adaptation quality, learning from failure
6. **Retrieval Quality** - Relevance, evidence accuracy, coverage, hallucination detection

### Features

- **LangGraph Integration**: Evaluation workflow orchestrated with LangGraph
- **Async Processing**: Full async support for high-performance evaluation
- **Detailed Analytics**: Comprehensive reports and dimension-specific insights
- **RESTful API**: Clean, well-documented API endpoints
        """,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def register_routes(router, prefix: str, tags: list[str]) -> None:
        """Register APIRouter routes eagerly for FastAPI versions with lazy includes."""
        for route in router.routes:
            if not isinstance(route, APIRoute):
                continue
            path = f"{prefix}{route.path}"
            app.add_api_route(
                path=path,
                endpoint=route.endpoint,
                methods=route.methods,
                response_model=route.response_model,
                status_code=route.status_code,
                tags=tags,
                summary=route.summary,
                description=route.description,
                response_description=route.response_description,
                responses=route.responses,
                deprecated=route.deprecated,
                name=route.name,
                include_in_schema=route.include_in_schema,
            )

    register_routes(tasks.router, "/api/v1/tasks", ["tasks"])
    register_routes(evaluation.router, "/api/v1/evaluations", ["evaluations"])
    register_routes(reports.router, "/api/v1/reports", ["reports"])
    register_routes(benchmark.router, "/api/v1/benchmark", ["benchmark"])
    register_routes(wiki_router.router, "", ["wiki-agent"])
    register_routes(wiki_chat.router, "", ["wiki-agent"])
    register_routes(workspace_router, "/api/v1", ["workspaces"])

    from app.api.auth_middleware import AuthMiddleware
    app.add_middleware(AuthMiddleware)
    @app.get("/health")
    async def health_check():
        """Health check with database connectivity."""
        from sqlalchemy import text
        db_status = "unknown"
        try:
            from app.db.database import async_session_factory
            async with async_session_factory() as session:
                await session.execute(text("SELECT 1"))
            db_status = "connected"
        except Exception:
            db_status = "disconnected"

        return {
            "status": "healthy" if db_status == "connected" else "degraded",
            "app": settings.APP_NAME,
            "version": "0.1.0",
            "database": db_status,
            "auth_enabled": settings.AUTH_ENABLED,
        }

    # Root endpoint
    @app.get("/")
    async def root():
        """Root endpoint with API information."""
        return {
            "name": settings.APP_NAME,
            "version": "0.1.0",
            "description": "Agent Runtime Evaluation Platform",
            "docs": "/docs",
            "health": "/health",
            "api": "/api/v1",
            "wiki_agent": "/api/wiki",
            "wiki_chat": "/api/chat",
        }

    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
