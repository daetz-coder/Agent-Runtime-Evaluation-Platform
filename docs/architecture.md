# Architecture Documentation

> **入口**: [README.md](../README.md) · **快速开始**: [getting_started.md](getting_started.md) · **设计**: [design.md](design.md) · **API**: [api.md](api.md)

## Overview

The Agent Runtime Evaluation Platform evaluates the runtime quality of AI agents across 6 key dimensions. The platform uses LangGraph for workflow orchestration and FastAPI for the API layer.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        API Layer (FastAPI)                       │
├─────────────────────────────────────────────────────────────────┤
│  /api/v1/tasks │ /api/v1/evaluations │ /api/v1/reports │ /api/v1/benchmark │
│  /api/wiki/* │ /api/chat/* │ /api/v1/settings │
│  CORS → CorrelationIdMiddleware → AuthMiddleware → RateLimitMiddleware     │
│  → PrometheusMiddleware (middleware chain)                                 │
└────────────────────┴───────────────────┴─────────────────┴───────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Service Layer                                 │
│  EvaluationService · ReplayService · JudgeService · DiffService          │
│  IncrementalEvalService · RegressionDetectionService · SystemHealth      │
└─────────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
┌──────────────────────────┐  ┌──────────────────────────────────┐
│   Redis Cache Layer      │  │   6 Parallel Evaluators           │
│   (可选, 优雅降级)       │  │   (asyncio.gather)                │
│                          │  │  ┌──────────┐ ┌──────────┐       │
│  • 报表聚合缓存 (5min)   │  │  │Planning  │ │Tactical  │       │
│  • LLM 结果缓存 (24h)    │  │  │Evaluator │ │Evaluator │       │
│  • Task 查询缓存 (1min)  │  │  └──────────┘ └──────────┘       │
│  • 接口限流 (Sorted Set) │  │  ┌──────────┐ ┌──────────┐       │
│  • Dashboard 计数 (30s)  │  │  │Tool Use  │ │ Memory   │       │
│  • Wiki 会话缓存 (1h)    │  │  │Evaluator │ │Evaluator │       │
│                          │  │  └──────────┘ └──────────┘       │
│  Redis 不可用时所有操作  │  │  ┌──────────┐ ┌──────────┐       │
│  静默返回 None/False     │  │  │ Replan   │ │Retrieval │       │
│                          │  │  │Evaluator │ │Evaluator │       │
└──────────────────────────┘  │  └──────────┘ └──────────┘       │
                              │  LLM-as-Judge + 幻觉检测          │
                              │  + _invoke_llm_cached()           │
                              └──────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Database Layer (SQLAlchemy Async)             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │  AgentTask  │  │ Trajectory  │  │ Evaluation  │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
│  ┌─────────────┐  ┌─────────────┐                               │
│  │  Workspace  │  │  AuditLog   │                               │
│  └─────────────┘  └─────────────┘                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│          Frontend (Vue 3 + Element Plus + ECharts)               │
│  Dashboard · Tasks · Evaluations · Analytics · Benchmark · Wiki │
│  6维雷达图 · 趋势线 · 热力图 · 相关性矩阵 · 单调性曲线          │
└─────────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. API Layer (FastAPI)

- **Tasks API**: Create and manage agent tasks
- **Evaluations API**: Run and retrieve evaluations
- **Reports API**: Get analytics and summaries
- **Middleware chain**: CORS → CorrelationIdMiddleware → AuthMiddleware → RateLimitMiddleware → PrometheusMiddleware

### 2. Service Layer

- **EvaluationService**: Orchestrates the evaluation process
- Manages database operations with integrated cache invalidation
- Integrates with LangGraph workflow

- **ReplayService** (`app/services/replay_service.py`): Step-by-step replay debugger.
  Extracts LLM trace data (`_llm_trace`) from trajectory steps and assembles
  a chronological replay view. API: `GET /evaluations/{id}/replay`.

- **JudgeService** (`app/services/judge_service.py`): Judge transparency panel.
  Extracts raw judge LLM prompt/response from evaluation feedback JSON
  (`_judge_raw`). API: `GET /evaluations/{id}/judge-raw[/{dim}]`.

- **DiffService** (`app/services/diff_service.py`): Trajectory comparison.
  Compares two trajectories step-by-step, detecting added/removed/changed steps.
  API: `GET /evaluations/diff`.

- **IncrementalEvalService** (`app/services/incremental_eval.py`): Partial
  re-evaluation. Detects trajectory changes → maps to affected evaluation
  dimensions → re-runs only affected evaluators. API: `POST /evaluations/incremental`.

- **RegressionDetectionService** (`app/services/regression_detection.py`):
  Score regression detection. Compares two evaluations with configurable
  per-dimension thresholds. API: `GET /evaluations/regression/check`.

### 3. Redis Cache Layer (`app/core/cache.py`)

可选的 Redis 缓存层，Redis 不可用时所有操作静默降级（返回 None/False）。

| 缓存类型 | Key 模式 | TTL | 数据结构 | 失效时机 |
|----------|----------|-----|----------|----------|
| 报表聚合 | `report:summary:{ws}`, `report:trends`, `report:dim:{dim}`, `report:compare:{id}` | 5–10min | String (JSON) | 评估完成时 `DEL report:*` |
| LLM 结果 | `llm:{EvaluatorName}:{prompt_hash}` | 24h | Hash | 永不过期（相同 prompt = 相同结果） |
| Task 查询 | `task:{task_id}` | 60s | String (JSON) | task 更新/删除/状态变更时 |
| Trajectory | `trajectory:{task_id}` | 5min | String (JSON) | 添加新步骤时 |
| Dashboard | `dashboard:{ws_id}:counters` | 30s | String (JSON) | task 创建/删除/更新时 |
| Wiki 会话 | `wiki:session:{id}`, `wiki:sessions:list`, `wiki:session:{id}:facts` | 1h / 60s | String (JSON) | 消息添加/会话更新/删除时 |
| 接口限流 | `ratelimit:eval:{client_id}` | 2×window | Sorted Set | 自动过期（滑动窗口） |

**限流算法**: Sorted Set 滑动窗口 — score 为时间戳，`ZREMRANGEBYSCORE` 清除过期条目，`ZCARD` 计数，超限返回 429 + `Retry-After`。

**关键实现**:
- `init_redis()` / `close_redis()` — lifespan 中管理连接池
- `cache_get/set/delete/delete_pattern` — 通用操作，2s 超时
- `check_rate_limit(key, limit, window)` — 原子 pipeline 限流
- `_invoke_llm_cached()` — BaseEvaluator 中的 LLM 缓存方法

### 4. LangGraph Workflow

The evaluation workflow is orchestrated using LangGraph:

1. **Validate Input**: Check required fields
2. **Parallel Evaluation**: Run 6 evaluators simultaneously (with LLM caching)
3. **Aggregate Results**: Combine scores and generate report

### 5. Evaluators

Each evaluator focuses on a specific dimension:

| Evaluator | Focus | Metrics |
|-----------|-------|---------|
| Planning | Plan quality | Coverage, Ordering, Granularity, Completeness |
| Tactical | Action decisions | Relevance, Efficiency, Correctness |
| Tool Use | Tool selection | Selection Quality, Parameter Accuracy, Result Utilization |
| Memory | Information retention | Retention, Relevance, Consistency |
| Replan | Replanning decisions | Trigger Appropriateness, Adaptation Quality, Learning |
| Retrieval | RAG / retrieval quality | Relevance, Evidence Accuracy, Coverage, Hallucination detection |


The Agent Runtime runs AI agents inside Docker sandbox containers and captures
their full trajectory for evaluation.

| Component | File | Description |
|-----------|------|-------------|
| **LangGraph Agent** | `graph.py` | ReAct loop: think → act → observe. Auto-injects `_llm_trace` (prompt/response/model/latency) into each step |
| **Prompts** | `prompts/` (package) | System prompt templates in `templates/v1.1.yaml`. Versioned via `PROMPT_VERSION=v1.1` constant |
| **TrajectoryCollector** | `sdk/collector.py` | Unified trajectory recorder for all agents. Records 14 action types with Pydantic schema validation |
| **Tools** | `tools/` | PythonExecute, BashExecute, FileRead/Write/List |

calls `get_mock_trajectory(goal)` → returns fixed 5-step trajectory with
`_llm_trace` → no Docker required.

### 8. Golden Test Suite (`app/benchmarks/golden/`)

Curated trajectories with expected score ranges for evaluator regression testing.

| Component | File | Description |
|-----------|------|-------------|
| **GoldenCase** | `__init__.py` | Data model: id, description, goal, trajectory, expected_ranges |
| **Case: Excellent** | `case_excellent.py` | 12-step perfect agent: data analysis pipeline, scores expected 80-100 |
| **Case: Tool Misuse** | `case_tool_misuse.py` | 6-step bad agent: no plan, repeated failures, scores expected 0-30 |
| **Case: Replan** | `case_replan.py` | 10-step agent: curl fail → 403 → replan → API success, replan 80-100 |
| **Case: Retrieval** | `case_retrieval.py` | 9-step RAG agent: multi-turn retrieval + evidence, retrieval 70-98 |
| **GoldenSuiteRunner** | `runner.py` | Run all/specific cases, fail-fast, print/summary |
| **CI Gate** | `run_ci_gate.py` | Two-stage: golden suite → optional regression check |

### 9. Database Models

- **AgentTask**: Stores task information
- **AgentTrajectory**: Stores execution steps (with optional `_llm_trace`)
- **Evaluation**: Stores evaluation results + version fields (`prompt_version`, `model_name`, `model_provider`, `evaluator_version`)

## Data Flow

```
1. Create Task → AgentTask
2. Add Trajectory → AgentTrajectory[]
3. Run Evaluation → LangGraph Workflow
4. Store Results → Evaluation
5. Return Report → `EvaluationResponse` (含 6 维分数 + 版本信息)
```

## Design Decisions

### Why LangGraph?

- **Visual Workflow**: Easy to understand evaluation flow
- **Parallel Execution**: Evaluators run concurrently
- **State Management**: Clean state passing between nodes
- **Extensibility**: Easy to add new evaluators

### Why Async?

- **Performance**: Non-blocking I/O for LLM calls
- **Scalability**: Handle multiple evaluations concurrently
- **Modern Python**: Best practices for FastAPI

### Why Separate Evaluators?

- **Modularity**: Each evaluator is independent
- **Testability**: Easy to mock and test
- **Extensibility**: Add new dimensions without changing existing code
- **Clarity**: Clear separation of concerns

### Why Redis Cache (Optional)?

- **报表性能**: 聚合查询涉及全表扫描，缓存后 Dashboard 响应 <10ms
- **LLM 成本**: 相同轨迹+目标的评估结果可复用（24h TTL），monotonicity benchmark 场景节省 10x+ API 调用
- **接口保护**: Sorted Set 滑动窗口限流，防止 LLM API 费用失控
- **优雅降级**: Redis 不可用时应用正常运行，仅失去缓存加速（所有 cache 操作 catch 异常后返回 None/False）
- **Key 前缀隔离**: `REDIS_KEY_PREFIX` 支持多实例共用同一 Redis 实例

### 10. Observability（可观测性）

三层可观测性，全部支持 graceful degradation（collector 不可用时自动 no-op）：

| 层 | 技术 | 模块 | 说明 |
|----|------|------|------|
| **链路追踪** | OpenTelemetry | `app/core/tracing.py` | 评估全链路 span 树，支持 Jaeger/Zipkin 可视化 |
| **指标监控** | Prometheus | `app/core/metrics.py` + `metrics_middleware.py` | HTTP/LLM/Tool/Sandbox 指标，`GET /metrics` 端点 |
| **结构化日志** | structlog | `app/core/logging.py` + `correlation_id_middleware.py` | JSON 格式日志，自动注入 request_id |

**Tracing span 树**：
```
evaluation
├── session_acquire → container_id
├── workspace_setup → file_count
├── agent_loop
│   ├── step_0_think_and_act → step_number, has_tool_call
│   │   ├── llm_call → provider, model, response_length
│   │   └── tool_execute → tool_name, success, duration_ms
│   └── step_N_think_and_act → ...
├── workspace_capture
├── session_release
├── trajectory_persist → step_count
└── evaluation → evaluator_count, parallel, overall_score
```

**关键指标**：
- `agent_eval_evaluation_total{status,mode}` — 评估计数
- `agent_eval_evaluation_duration_seconds{mode}` — 评估耗时分布
- `agent_eval_llm_calls_total{provider,model}` — LLM 调用计数
- `agent_eval_tool_calls_total{tool,status}` — 工具调用计数

### 11. Celery Task Queue（任务队列）

评估任务通过 Celery + Redis 异步执行，替代 FastAPI BackgroundTasks：

| 特性 | 说明 |
|------|------|
| **自动重试** | 指数退避（15s, 30s, 45s），最多 3 次 |
| **并发控制** | `worker_prefetch_multiplier=1`，防止 worker 抢占多个长时间任务 |
| **队列分离** | `evaluation` 队列 |
| **任务超时** | soft limit = AGENT_TIMEOUT + 60s，hard limit = AGENT_TIMEOUT + 120s |
| **Worker 重启** | `max_tasks_per_child=50`，防止内存泄漏 |
| **Fallback** | Celery 不可用时自动降级到 BackgroundTasks |

### 12. Webhook Retry（通知重试）

评估完成后通过 Webhook 通知外部系统，指数退避重试：

```
attempt 1: delay=0s  → POST webhook_url
attempt 2: delay=1s  → POST webhook_url (retry)
attempt 3: delay=2s  → POST webhook_url (retry)
attempt 4: delay=4s  → POST webhook_url (final retry)
→ 全部失败: 记录日志，不阻塞评估流程
```

---

## Tech Stack

| Category | Technology | Purpose |
|----------|-----------|---------|
| **Backend Framework** | FastAPI + Uvicorn | REST API + SSE streaming, fully async |
| **Agent Orchestration** | LangGraph + LangChain | Agent ReAct loop, evaluation workflow graph |
| **AI Models** | DeepSeek / GLM / Qwen / OpenAI | LLM inference + LLM-as-Judge evaluation |
| **Vector Search** | Milvus Lite + BM25 (RRF) | Wiki Agent hybrid search (vector + keyword) |
| **Database** | SQLAlchemy Async + SQLite / PostgreSQL | Persistence with Alembic migration management |
| **Cache** | Redis (optional, graceful degradation) | LLM response cache, report aggregation, rate limiting |
| **Frontend** | Vue 3 + TypeScript + Element Plus + ECharts | Management panel and data visualization |
| **Container** | Docker | Agent sandbox isolation |
| **Observability** | OpenTelemetry + Prometheus + structlog | Distributed tracing, metrics, structured logging |
| **Task Queue** | Celery (optional, graceful degradation) | Async evaluation tasks with exponential backoff |
| **Data Science** | sentence-transformers + CrossEncoder | Reranker for retrieval re-ranking |
| **SDK** | Python SDK (httpx + langchain-core) | Zero-instrumentation trajectory collection |

## Key Points

### Architectural Decisions

1. **LangGraph over linear pipeline** — State graph enables clean parallel execution of 6 evaluators, easy to add new dimensions without affecting existing logic
2. **Redis as optional dependency** — All cache operations catch exceptions and return None/False when Redis is unavailable; app core functionality is never blocked by cache layer
3. **Separate evaluators over monolithic judge** — Each evaluator is independently testable; changes to one dimension's judge prompt won't affect others
4. **Cache key includes model name** — `llm:{Evaluator}:{Model}:{prompt_hash}` ensures multi-model consensus evaluators don't share a single cached response
5. **SSE streaming over polling** — Real-time push of agent steps and evaluation progress, enabling live UI updates without client polling

## Effect Display

### Frontend Visualization Reference

| Page | Components | Description |
|------|------------|-------------|
| **Dashboard** | Radar chart, trend line chart, bar chart, stat cards | 6-dimension capability overview, score trends over time |
| **Tasks** | Task list with filters, table view | CRUD management, status/skip/limit filtering |
| **Evaluations** | Filterable evaluation list | Status and score range filtering |
| **Evaluation Detail** | Score cards, radar chart, trajectory timeline | Per-dimension breakdown, LLM judge transparency, replay debugger |
| **Analytics** | Distribution chart, correlation heatmap, performance heatmap | Score distribution, dimensional correlation analysis, suggestions |
| **Settings** | System status indicators, configuration forms | Health status (Redis/Milvus/DB/ReRank), runtime config |

### Score Quality Scale

| Level | Range | Color | Meaning |
|-------|-------|-------|---------|
| **优秀 (Excellent)** | 80-100 | 🟢 Green | Agent performs well across all dimensions |
| **良好 (Good)** | 60-79 | 🟡 Yellow | Generally good, minor improvements needed |
| **一般 (Fair)** | 40-59 | 🟠 Orange | Noticeable issues in multiple dimensions |
| **较差 (Poor)** | 0-39 | 🔴 Red | Significant problems, requires substantial improvement |

### Data Flow for Visualization

```
Trajectory Data
    │
    ▼
EvaluationService.evaluate()
    │
    ├── asyncio.gather(6 evaluators)
    │   ├── PlanningEvaluator → scores + feedback
    │   ├── TacticalEvaluator → scores + feedback
    │   ├── ToolUseEvaluator → scores + feedback
    │   ├── MemoryEvaluator  → scores + feedback
    │   ├── ReplanEvaluator  → scores + feedback
    │   └── RetrievalEvaluator → scores + feedback
    │
    ▼
OverallEvaluation (aggregated)
    │
    ├── DB Storage → Evaluation model
    ├── Cache Invalidation → report:* + dashboard:*
    │
    ▼
Frontend
    ├── Dashboard → HTTP GET /reports/summary + /reports/trends
    ├── EvaluationDetail → HTTP GET /evaluations/{id}
    ├── Replay Debugger  → HTTP GET /evaluations/{id}/replay
    ├── Judge Panel      → HTTP GET /evaluations/{id}/judge-raw
    └── Analytics        → HTTP GET /reports/dimensions/{dim} + /reports/trends
```
