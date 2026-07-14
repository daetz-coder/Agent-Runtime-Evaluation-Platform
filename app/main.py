"""
FastAPI application entry point.

Agent Runtime Evaluation Platform
- Evaluate Planning, Tool Use, Memory, and Replanning
- Built with LangGraph, FastAPI, and Python
"""

import os

# Fix gRPC "too_many_pings" GOAWAY from ChromaDB/Milvus — set before any gRPC client
os.environ.setdefault("GRPC_ARG_KEEPALIVE_TIME_MS", "120000")
os.environ.setdefault("GRPC_ARG_KEEPALIVE_TIMEOUT_MS", "20000")
os.environ.setdefault("GRPC_HTTP2_MAX_PINGS_WITHOUT_DATA", "0")
os.environ.setdefault("GRPC_ARG_HTTP2_MIN_RECV_PING_INTERVAL_WITHOUT_DATA_MS", "5000")

# Suppress FAISS AVX2 module load warning on Windows (falls back cleanly to generic)
os.environ.setdefault("FAISS_OPT_LEVEL", "generic")

# Initialize structured logging BEFORE any other imports that use logging
from app.core.logging import get_logger, setup_logging  # noqa: E402

setup_logging()

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from app.api.v1.endpoints import benchmark, evaluation, reports, system, tasks
from app.core.cache import close_redis, init_redis
from app.core.config import settings
from app.db.database import close_db, init_db
from app.wiki_agent.bootstrap import startup as wiki_agent_startup
from app.wiki_agent.routers import chat as wiki_chat
from app.wiki_agent.routers import debug as wiki_debug
from app.wiki_agent.routers import vector_admin as wiki_vector_api
from app.wiki_agent.routers import wiki as wiki_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    logger.info("Starting %s...", settings.APP_NAME)
    if not settings.AUTH_ENABLED:
        logger.warning(
            "⚠️  Authentication is DISABLED (AUTH_ENABLED=false). "
            "All endpoints are accessible without credentials. "
            "Enable authentication before deploying to production."
        )
    await init_db()
    logger.info("Database initialized")
    await init_redis()
    logger.info("Starting Wiki Agent...")
    await wiki_agent_startup()
    logger.info("Wiki Agent initialized")

    # Initialize OpenTelemetry tracing
    from app.core.tracing import init_tracing

    tracing_ok = init_tracing()
    logger.info("Tracing: %s", "active" if tracing_ok else "disabled")

    # Set app info metric
    from app.core.metrics import APP_INFO

    APP_INFO.info(
        {
            "version": "0.1.0",
            "environment": settings.APP_ENV,
        }
    )

    yield
    logger.info("Shutting down...")

    from app.core.tracing import shutdown_tracing

    shutdown_tracing()
    await close_redis()
    await close_db()
    logger.info("Database connections closed")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        description="""
# Agent Runtime Evaluation Platform

AI Agent 全维度评估平台，通过 SDK 轨迹采集覆盖规划、决策、工具使用、记忆、重规划、检索 6 大能力维度。

---

## 📐 系统架构

```
┌───────────────┐     ┌───────────────────┐     ┌──────────────────┐
│   Frontend    │────▶│   FastAPI Server   │◀────│   SDK Collector  │
│  (Vue 3 +     │◀────│  (Python 3.14)    │     │  (Agent 轨迹采集) │
│   Element+)   │     │                   │     └──────────────────┘
└───────────────┘     ├───────────────────┤
                      │   Evaluators × 6  │
                      │   (LLM Judge)     │
                      ├───────────────────┤     ┌──────────────────┐
                      │   Redis Cache     │     │   SQLite / PG    │
                      │   (LLM 响应/会话) │     │   (任务/轨迹/评估)│
                      └───────────────────┘     └──────────────────┘
```

## 🛠️ 技术栈

| 层次 | 技术 | 用途 |
|---|---|---|
| **后端框架** | FastAPI + Uvicorn | REST API + SSE 实时流 |
| **Agent 编排** | LangGraph | Agent 状态图/工作流 |
| **AI 模型** | DeepSeek / GLM / Qwen / OpenAI | LLM 推理与评估裁判 |
| **向量检索** | Milvus Lite + BM25 (RRF) | RAG 知识库混合检索 |
| **数据库** | SQLite (dev) / PostgreSQL (prod) + Redis | 持久化 + 缓存 |
| **前端** | Vue 3 + Element Plus + TypeScript | 管理面板与可视化 |
| **采集 SDK** | Python SDK (HTTP) | Trajectory 自动埋点 |

## 🔑 关键特性

- **SDK 评测** — 外部 SDK 埋点轨迹评测
- **6 维评分** — Planning、Tactical、Tool Use、Memory、Replan、Retrieval
- **多模型共识** — 跨厂商（DeepSeek + GLM + Qwen）独立评分，输出均值和置信度
- **增量评估** — 回归检测，比较历史评分变化趋势
- **LLM 响应缓存** — Redis 缓存 LLM 调用，多模型共识时按模型名隔离缓存
- **实时流式评测** — SSE 推送评测进度与中间结果
- **RAG 知识库** — 基于 Milvus + BM25 混合检索的 Wiki Agent
- **OpenTelemetry 链路追踪** — 可选集成，支持导出到 Jaeger/Collector

## 🚀 快速开始

### SDK 埋点模式
```python
import asyncio
from sdk import get_collector

async def main():
    collector = get_collector()
    task_id = await collector.start("分析项目依赖")
    collector.record_plan(steps=[...])
    collector.record_tool_call(name="bash", input="pip list --outdated", output="...")
    await collector.finish()

asyncio.run(main())
```
→ SDK 将轨迹上报至平台 → 异步完成评估

## 📊 效果展示

### 评估仪表盘
- **任务列表** — 按状态/工作空间筛选，搜索目标关键词
- **评分趋势** — 6 维度雷达图 + 历史趋势折线
- **评分分布** — 各分数段的统计直方图

### 评估详情页
- **Trajectory 时间线** — 可视化回放 Agent 执行步骤
- **打分明细** — 每个维度的 LLM Judge 原始 Prompt / Response
- **多模型对比** — Consensus 模式下各厂商评分横向对比
- **回归检测** — 与历史评估的分数变化对比

### 系统管理
- **健康检查** — Redis / Milvus / 数据库 / ReRank 状态一览
- **缓存管理** — 手动刷新/清除各缓存

## 📂 API 总览

| 分组 | 前缀 | 说明 |
|---|---|---|
| **评估** | `/api/v1/evaluations/` | 创建、运行、流式评测、共识评估、批量评估 |
| **任务** | `/api/v1/tasks/` | 任务 CRUD、轨迹提交 |
| **报告** | `/api/v1/reports/` | 评分报告、趋势分析、回归检测 |
| **系统** | `/api/v1/system/` | 健康检查、配置查看 |
| **系统** | `/api/v1/system/` | 健康检查与诊断 |
| **基准** | `/api/v1/benchmark/` | 性能基准测试 |

---
> **Version:** 0.1.0 | **Swagger UI:** `/docs` | **ReDoc:** `/redoc` | **文档:** [docs/](https://github.com/daetz-coder/Agent-Runtime-Evaluation-Platform/tree/main/docs)
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
    register_routes(system.router, "/api/v1/system", ["system"])
    register_routes(wiki_router.router, "", ["wiki-agent"])
    register_routes(wiki_chat.router, "", ["wiki-agent"])
    register_routes(wiki_vector_api.api_router, "", ["wiki-agent"])
    register_routes(wiki_vector_api.page_router, "", ["wiki-agent"])
    register_routes(wiki_debug.router, "", ["debug"])

    from app.api.rate_limit_middleware import RateLimitMiddleware

    app.add_middleware(RateLimitMiddleware)

    from app.api.correlation_id_middleware import CorrelationIdMiddleware

    app.add_middleware(CorrelationIdMiddleware)

    from app.api.metrics_middleware import PrometheusMiddleware

    app.add_middleware(PrometheusMiddleware)

    @app.get("/health")
    async def health_check():
        """Health check with database and Wiki Agent index status."""
        from app.services.system_health import get_system_health

        return await get_system_health()

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
            "vector_admin": "/vector-admin",
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
