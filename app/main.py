"""
FastAPI application entry point.

Agent Runtime Evaluation Platform
- Evaluate Planning, Tool Use, Memory, and Replanning
- Built with LangGraph, FastAPI, and Python
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.database import init_db, close_db
from app.api.v1 import api_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    # Startup
    print(f"Starting {settings.APP_NAME}...")
    await init_db()
    print("Database initialized")

    yield

    # Shutdown
    print("Shutting down...")
    await close_db()
    print("Database connections closed")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        description="""
## Agent Runtime Evaluation Platform

Evaluate the runtime quality of AI agents across 5 dimensions:

1. **Planning Quality** - Coverage, ordering, granularity, completeness
2. **Tactical Decisions** - Relevance, efficiency, correctness of next actions
3. **Tool Use** - Selection quality, parameter accuracy, result utilization
4. **Memory** - Retention, relevance, consistency of recalled information
5. **Replanning** - Trigger appropriateness, adaptation quality, learning from failure

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

    # Include API routes
    app.include_router(api_router, prefix="/api/v1")

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "app": settings.APP_NAME,
            "version": "0.1.0",
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
