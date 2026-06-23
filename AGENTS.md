# Agent Runtime Evaluation Platform

AI Agent 运行时质量评估平台 — 评估 Planning、Tactical、Tool Use、Memory、Replan、Retrieval 六个维度，使用 LangGraph 编排评估工作流。

## Project

- **Stack**: Python 3.11+ / FastAPI / LangGraph / SQLAlchemy (async) + Vue 3 / TypeScript / Vite / Element Plus / ECharts
- **Backend entry**: `python -m app.main` → uvicorn on `0.0.0.0:8000`
- **Frontend entry**: `cd frontend && npm run dev` → Vite on `localhost:3000`
- **One-click (Windows)**: `start.bat` — starts both backend + frontend
- **Default LLM**: DeepSeek (`deepseek-v4-flash`) via OpenAI-compatible API; also supports Anthropic and OpenAI
- **Database**: SQLite by default (`sqlite+aiosqlite:///./agent_eval.db`); PostgreSQL via asyncpg optionally

## Commands

| What | Command |
|------|---------|
| Install (backend) | `pip install -e ".[dev]"` |
| Run backend | `python -m app.main` |
| Run frontend | `cd frontend && npm run dev` |
| Run tests | `pytest` (asyncio_mode=auto, testpaths=tests) |
| Coverage | `pytest --cov=app --cov-report=term` |
| Lint (Python) | `ruff check .` |
| Type check | `mypy .` |
| Lint (frontend) | `cd frontend && npm run lint` |
| Build frontend | `cd frontend && npm run build` |
| Quick smoke test | `python test_api.py` (manual httpx script against localhost:8000) |

## Architecture

```
frontend/src/          Vue 3 SPA — Element Plus + ECharts
  views/               Dashboard, Tasks, Evaluations, Analytics, Benchmark, WikiAgent, Settings
  api/                 Axios API client

app/main.py            FastAPI app factory + lifespan (DB init, Wiki Agent bootstrap)
app/api/v1/endpoints/  REST routers: tasks, evaluation, reports, benchmark
app/services/          EvaluationService — business logic, orchestrates LangGraph graphs
app/graphs/            evaluation_graph.py — LangGraph StateGraph (validate → parallel eval → aggregate)
app/evaluators/        6 evaluators (planning, tactical, tool_use, memory, replan, retrieval)
app/benchmarks/        Monotonicity benchmark trajectories + SSE runner
app/models/            Pydantic schemas (API) + ActionType constants (trajectory action types)
app/db/                SQLAlchemy ORM models (AgentTask, AgentTrajectory, Evaluation) + async session
app/adapters/          Pluggable adapters: langgraph (instrument), llm_proxy, callback
app/collectors/        trajectory.py — trajectory step collection
app/wiki_agent/        Integrated RAG Wiki Agent (Chromadb, sentence-transformers, BM25)
app/core/config.py     pydantic-settings from .env, case-sensitive
```

**Evaluation flow**: Task created → trajectory steps pushed → evaluation triggered → 6 evaluators run in parallel (default) → scores aggregated into `OverallEvaluation` → stored in DB. Optional SSE stream via `POST /evaluations/stream` with live progress.

## Conventions

- **Python style**: ruff (line-length 120, E/F/I/N/W/UP), mypy strict, all public symbols have docstrings
- **Async first**: all DB operations are async (AsyncSession via `Depends(get_db)`), all evaluators are async, LangGraph graph is async
- **Evaluator pattern**: extend `BaseEvaluator`, accept optional `llm` override, use LLM-as-judge via `langchain_core.prompts.ChatPromptTemplate`. Evaluators live in `app/evaluators/`, registered in `__init__.py`
- **API pattern**: endpoint → `EvaluationService` (business logic) → LangGraph graph → evaluators. Pydantic models define request/response shapes in `app/models/schemas.py`
- **DB models**: SQLAlchemy 2.0 `Mapped[]` style, `DeclarativeBase`, UTC timestamps via `_utcnow()`, use `datetime.now(timezone.utc)` not `datetime.utcnow()`
- **Trajectory steps**: use `ActionType` constants (`ActionType.PLAN`, `ActionType.TOOL_CALL`, etc.) — never raw strings
- **Frontend**: Vue 3 Composition API `<script setup>`, auto-imports for Element Plus components, route-based code splitting, Pinia for state
- **Config**: `.env` file, `pydantic-settings`, field names UPPER_CASE. `DEFAULT_LLM_PROVIDER` selects which LLM evaluators use

## Notes

<!-- Add project-specific notes here as you go -->
