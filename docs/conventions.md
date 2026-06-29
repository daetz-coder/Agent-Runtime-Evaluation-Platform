# 项目约定与开发规范

> **入口**: [README.md](../README.md) · **开发者指南**: [developer_guide.md](developer_guide.md) · **架构**: [architecture.md](architecture.md)

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
| Run backend (mock mode, no Docker) | `SANDBOX_MOCK_MODE=true python -m app.main` |
| Run frontend | `cd frontend && npm run dev` |
| Docker Compose | `docker compose up --build` |
| DB migration | `alembic upgrade head` |
| Run tests | `make test` or `pytest tests/ -v` |
| Run tests with coverage | `make test-cov` |
| Python lint | `make lint` or `ruff check .` |
| Type check | `make typecheck` or `mypy .` |
| Golden Test Suite | `make golden` |
| CI Gate (golden + regression) | `make check-ci` |
| Regression check | `make check-regression BASE=<id> HEAD=<id>` |
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

app/main.py           FastAPI app + lifespan (DB init, Redis init, Wiki Agent bootstrap, Milvus load)
app/api/v1/endpoints/ tasks / evaluation / reports / benchmark
app/api/              auth_middleware.py / rate_limit_middleware.py / workspace.py (多租户+RBAC)
app/core/             pydantic-settings 配置 + cache.py (Redis 缓存层, 优雅降级)
app/services/         
  evaluation_service.py  6 维评估编排 (默认并行, EVAL_PARALLEL=true)
  replay_service.py      Replay 调试器 — 每步 LLM 原始 prompt/response
  judge_service.py       Judge 透明度面板 — 原始 judge prompt/response
  diff_service.py        Trajectory Diff — 步骤级对比 (added/removed/changed)
  incremental_eval.py    增量评估 — 仅重算变化维度
  regression_detection.py 回归检测 — 自动发现分数退化
app/evaluators/       6 evaluators (planning/tactical/tool_use/memory/replan/retrieval) + LLM 缓存
app/evaluators/consensus.py  多模型共识 (DeepSeek+GLM+Qwen → mean±std)
app/graphs/           LangGraph 串行 fallback + evaluate_parallel() asyncio.gather
app/benchmarks/       
  monotonicity.py     Monotonicity benchmark (6 档质量递减 → 单调性验证)
  run_ci_gate.py      CI 门禁 (golden suite + regression)
  golden/             Golden Test Suite — 4 条黄金轨迹 + 预期分数范围
app/agent_runtime/    
  runner.py           Agent Runtime 沙箱执行引擎
  graph.py            LangGraph ReAct agent 循环 (自动注入 _llm_trace)
  prompts/            系统提示词包 (PROMPT_VERSION=v1.1, templates/v1.1.yaml)
  mock_executor.py    Mock 模式 — 无需 Docker 返回预定义轨迹
  sandbox/            Docker 沙箱容器管理 (SessionPool + WorkspaceManager)
  tools/              沙箱内工具 (python/bash/file)
app/models/           Pydantic schemas + ActionType (14 种)
app/db/               SQLAlchemy ORM (AgentTask/Trajectory/Evaluation/Workspace/AuditLog)
app/wiki_agent/       RAG Wiki Agent (Milvus + BM25 + BGE-M3 + RRF + Redis 会话缓存)
Makefile              开发常用命令 (lint/test/golden/check-ci/run)
```

**Evaluation flow**: Task created → trajectory pushed → 6 evaluators run in parallel (~15s) → `OverallEvaluation` persisted. Also: SSE stream via `POST /evaluations/stream`, consensus via `POST /evaluations/consensus`, benchmark via `GET /benchmark/monotonicity`.

**Replay Debugger**: Agent Runtime 自动捕获每步 LLM prompt/response → `_llm_trace` 注入 trajectory → `GET /evaluations/{id}/replay` 查看。

**Judge Transparency**: 每个 evaluator 的 `_invoke_llm_cached()` 自动保存原始 prompt/response → `_judge_raw` 存入 feedback JSON → `GET /evaluations/{id}/judge-raw` 查看。

**Mock Mode**: `SANDBOX_MOCK_MODE=true` 启动后无需 Docker，Agent Runtime 返回固定轨迹。适合本地快速迭代 prompt。

**Incremental Eval**: `POST /evaluations/incremental` 对比两次 trajectory diff → 只重算变化维度 → 复用基线分数。

**Golden Test Suite**: 4 条精心构造的轨迹 + 预期分数范围。`make golden` 运行验证 evaluator 修改是否引入回归。

## Conventions

- **Python**: ruff (line-length 120), mypy strict, public symbols have docstrings
- **Async**: all DB async, evaluators async, use `async/await` not sync wrappers
- **Evaluator**: extend `BaseEvaluator`, use LLM-as-judge via `ChatPromptTemplate`, use `_invoke_llm_cached()` for Redis-backed LLM calls
- **Evaluator raw data**: override `_invoke_llm_cached()` automatically captures `_judge_raw`. Access via `evaluator.get_judge_raw_history()`.
- **DB**: SQLAlchemy 2.0 `Mapped[]`, UTC via `datetime.now(timezone.utc)`, never `datetime.utcnow()`
- **Trajectory**: use `ActionType.PLAN` etc., never raw strings. LLM trace goes into `action_detail["_llm_trace"]`.
- **Frontend**: Vue 3 `<script setup>`, Element Plus auto-import, route-based code splitting
- **Config**: `.env` via pydantic-settings, UPPER_CASE fields. Secrets never committed.
- **Redis**: optional dependency — all cache operations degrade gracefully (return None/False) when Redis is unavailable. Use `app.core.cache` helpers, never raw redis calls. Key prefix: `eval:` (configurable via `REDIS_KEY_PREFIX`). Cache invalidation on write — never rely on TTL alone for stale data.
- **Wiki Agent**: chunking uses `RecursiveCharacterTextSplitter` (LangChain), multi-format via `load_document()` (PDF/Word/MD/TXT)
- **Versioning**: `app/agent_runtime/prompts/__init__.py:PROMPT_VERSION` — incremented when system prompt changes. Stored in each `Evaluation.prompt_version` for traceability.

## Notes

<!-- Add project-specific notes here as you go -->
