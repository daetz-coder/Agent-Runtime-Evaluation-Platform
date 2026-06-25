# Agent Runtime Evaluation Platform

AI Agent 运行时质量评估平台 — 六维评估（Planning/Tactical/Tool Use/Memory/Replan/Retrieval），LangGraph 编排 + 并行执行 + 多模型共识。

## Project

- **Stack**: Python 3.11+ / FastAPI / LangGraph / Milvus / SQLAlchemy (async) + Vue 3 / TypeScript / Vite / Element Plus / ECharts
- **Backend entry**: `python -m app.main` → uvicorn on `0.0.0.0:8000`
- **Frontend entry**: `cd frontend && npm run dev` → Vite on `localhost:3000`
- **Docker**: `docker compose up --build`
- **Default LLM**: DeepSeek; also supported: GLM-4 (ZhipuAI), Qwen (DashScope), OpenAI, Anthropic
- **Database**: SQLite by default; PostgreSQL optional

## Commands

| What | Command |
|------|---------|
| Install (backend) | `pip install -e ".[dev]"` |
| Run backend | `python -m app.main` |
| Run frontend | `cd frontend && npm run dev` |
| Docker Compose | `docker compose up --build` |
| DB migration | `alembic upgrade head` |
| Run tests | `pytest tests/ -v` |
| Python lint | `ruff check .` |
| Type check | `mypy .` |
| Benchmark: multi-trajectory | `python -m tests.benchmark_score_distribution` |
| Benchmark: multi-model cost | `python -m tests.benchmark_multimodel` |
| Eval: accuracy verification | `python -m tests.eval_evaluator_accuracy` |
| Eval: Wiki retrieval | `python -m tests.eval_retrieval_standalone` |
| Adapters integration test | `python -m tests.test_adapters` |

## Architecture

```
sdk/                  独立 SDK 包 — 外部项目 pip install httpx langchain-core 即可用
  collector.py        TrajectoryCollector (线程安全, 批量上传, 离线模式)
  adapters/           instrument_langgraph / create_proxy_llm / create_callback_handler

app/main.py           FastAPI app + lifespan (DB init, Wiki Agent bootstrap, Milvus load)
app/api/v1/endpoints/ tasks / evaluation / reports / benchmark
app/api/              auth_middleware.py / workspace.py (多租户+RABC)
app/services/         EvaluationService — 6 维评估编排 (默认并行, EVAL_PARALLEL=true)
app/evaluators/       6 evaluators (planning/tactical/tool_use/memory/replan/retrieval)
app/evaluators/consensus.py  多模型共识 (DeepSeek+GLM+Qwen → mean±std)
app/graphs/           LangGraph 串行 fallback + evaluate_parallel() asyncio.gather
app/benchmarks/       Monotonicity benchmark (6 档质量递减 → 单调性验证)
app/models/           Pydantic schemas + ActionType (14 种)
app/db/               SQLAlchemy ORM (AgentTask/Trajectory/Evaluation/Workspace/AuditLog)
app/wiki_agent/       RAG Wiki Agent (Milvus + BM25 + BGE-M3 + RRF)
```

**Evaluation flow**: Task created → trajectory pushed → 6 evaluators run in parallel (~15s) → `OverallEvaluation` persisted. Also: SSE stream via `POST /evaluations/stream`, consensus via `POST /evaluations/consensus`, benchmark via `GET /benchmark/monotonicity`.

## Conventions

- **Python**: ruff (line-length 120), mypy strict, public symbols have docstrings
- **Async**: all DB async, evaluators async, use `async/await` not sync wrappers
- **Evaluator**: extend `BaseEvaluator`, use LLM-as-judge via `ChatPromptTemplate`, register in `__init__.py`
- **DB**: SQLAlchemy 2.0 `Mapped[]`, UTC via `datetime.now(timezone.utc)`, never `datetime.utcnow()`
- **Trajectory**: use `ActionType.PLAN` etc., never raw strings
- **Frontend**: Vue 3 `<script setup>`, Element Plus auto-import, route-based code splitting
- **Config**: `.env` via pydantic-settings, UPPER_CASE fields. Secrets never committed.
- **Wiki Agent**: chunking uses `RecursiveCharacterTextSplitter` (LangChain), multi-format via `load_document()` (PDF/Word/MD/TXT)

## Notes

<!-- Add project-specific notes here as you go -->
