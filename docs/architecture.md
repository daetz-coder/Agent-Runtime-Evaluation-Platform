# Architecture Documentation

## Overview

The Agent Runtime Evaluation Platform evaluates the runtime quality of AI agents across 6 key dimensions. The platform uses LangGraph for workflow orchestration and FastAPI for the API layer.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        API Layer (FastAPI)                       │
├─────────────────────────────────────────────────────────────────┤
│  /api/v1/tasks │ /api/v1/evaluations │ /api/v1/reports │ /api/v1/benchmark │
│  /workspaces   │ /api/wiki/*         │ /api/chat/*     │                   │
│  AuthMiddleware → RateLimitMiddleware → CORS (middleware chain)  │
└────────────────────┴───────────────────┴─────────────────┴───────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Service Layer                                 │
│  EvaluationService · ConsensusEvaluator · BenchmarkRunner       │
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
- **Middleware chain**: CORS → AuthMiddleware → RateLimitMiddleware

### 2. Service Layer

- **EvaluationService**: Orchestrates the evaluation process
- Manages database operations with integrated cache invalidation
- Integrates with LangGraph workflow

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

### 6. Database Models

- **AgentTask**: Stores task information
- **AgentTrajectory**: Stores execution steps
- **Evaluation**: Stores evaluation results

## Data Flow

```
1. Create Task → AgentTask
2. Add Trajectory → AgentTrajectory[]
3. Run Evaluation → LangGraph Workflow
4. Store Results → Evaluation
5. Return Report → OverallEvaluation
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
