# Agent Runtime Evaluation Platform — 完整技术文档（合集版）

> 版本：v2.0 | 最后更新：2026-07-06
> 本文档整合项目所有技术文档，覆盖背景、架构、实现、难点、面试问答。
> 原始内容来自：platform-overview.md、data-collection-architecture.md、tech-stack-rationale.md、architecture.md、design.md、deep-dive-evaluation-platform.md

---

# Agent Runtime Evaluation Platform 项目全面解析

> AI Agent 运行时全维度质量评估平台 — 对 Agent 的规划、战术决策、工具使用、记忆保持、重规划、RAG 检索质量六个维度进行量化评估。

---

## 目录

- [一、项目概述](#一项目概述)
- [二、技术栈](#二技术栈)
- [三、目录结构与文件功能](#三目录结构与文件功能)
  - [3.1 核心配置与基础设施层](#31-核心配置与基础设施层)
  - [3.2 数据库与模型层](#32-数据库与模型层)
  - [3.3 评估引擎层](#33-评估引擎层)
  - [3.4 服务层](#34-服务层)
  - [3.5 Agent 运行时层](#35-agent-运行时层)
  - [3.6 SDK 轨迹采集层](#36-sdk-轨迹采集层)
  - [3.7 API 路由层](#37-api-路由层)
  - [3.8 前端层](#38-前端层)
  - [3.9 基准测试与脚本](#39-基准测试与脚本)
  - [3.10 测试套件](#310-测试套件)
- [四、架构设计](#四架构设计)
  - [4.1 整体架构图](#41-整体架构图)
  - [4.2 评估工作流图](#42-评估工作流图)
  - [4.3 Agent 运行时流程图](#43-agent-运行时流程图)
  - [4.4 SDK 轨迹采集架构](#44-sdk-轨迹采集架构)
  - [4.5 6 维评估体系](#45-6-维评估体系)
  - [4.6 增量评估与回归检测](#46-增量评估与回归检测)
- [五、数据流](#五数据流)
  - [5.2 SDK 埋点模式数据流](#52-sdk-埋点模式数据流)
  - [5.3 评估引擎数据流](#53-评估引擎数据流)
  - [5.4 SSE 流式评测数据流](#54-sse-流式评测数据流)
- [六、API 接口一览](#六api-接口一览)
- [七、关键设计决策](#七关键设计决策)

---

## 一、项目概述

Agent Runtime Evaluation Platform 是一个 **AI Agent 运行时全维度质量评估平台**，核心定位是：

```
❌ 不是 Prompt Evaluation（评估 Agent 最终输出文本质量）
✅ Agent Runtime Evaluation（评估 Agent 运行时的行为质量）
```

**核心能力**：
1. **双模评测**：Sandbox 自动化评测（Agent 在 Docker 沙箱中运行）/ 外部 SDK 埋点轨迹评测
2. **6 维评分体系**：Planning / Tactical / Tool Use / Memory / Replan / Retrieval，共 20 项子指标
3. **多模型共识**：跨厂商（DeepSeek + GLM + Qwen）独立评分，输出均值和置信度
4. **增量评估**：Trajectory Diff 检测变化维度，只重算受影响项，节省约 2/3 时间
5. **回归检测**：自动对比基线分数，发现退化维度并告警
6. **SSE 流式评测**：实时推送 Agent 执行步骤 + 6 维评估进度
7. **Replay 调试器**：回放 Agent 每步 LLM 原始 Prompt / Response / Model / Latency
8. **Judge 透明面板**：公开每个维度的评分依据（原始 Judge Prompt / Response 可查）

**三大子系统**：

| 子系统 | 说明 |
|--------|------|
| **评估引擎** | 6 个并行 LLM-as-Judge 评估器，对轨迹进行多维度评分 |
| **Agent Runtime** | 基于 SDK 采集的轨迹进行 6 维评分 |
| **Wiki Agent** | 基于 RAG 的知识库问答 Agent，形成"运行-评估-改进"闭环 |

---

## 二、技术栈

| 类别 | 技术 | 用途 |
|------|------|------|
| 后端框架 | FastAPI + Uvicorn | REST API + SSE 实时流，全异步 |
| Agent 编排 | LangGraph + LangChain | Agent ReAct 循环、评估工作流 |
| AI 模型 | DeepSeek / GLM / Qwen / OpenAI / Anthropic | LLM 推理 + LLM-as-Judge 评估裁判 |
| 向量检索 | Milvus Lite + BM25 (RRF) | RAG 知识库混合检索（向量 + 关键词） |
| 数据库 | SQLAlchemy Async + SQLite / PostgreSQL | 持久化存储，Alembic 迁移管理 |
| 缓存 | Redis（可选，优雅降级） | LLM 响应缓存、报表聚合、接口限流 |
| 前端 | Vue 3 + TypeScript + Element Plus + ECharts | 管理面板与可视化图表 |
| 容器 | Docker（部署容器化） | 容器化部署 |
| 可观测性 | OpenTelemetry + Prometheus + structlog | 链路追踪、指标监控、结构化日志 |
| SDK | Python SDK（httpx + langchain-core） | 零侵入轨迹采集，三种集成模式 |

---

## 三、目录结构与文件功能

### 3.1 核心配置与基础设施层

```
app/
├── main.py                          # ★ FastAPI 应用入口（路由注册、中间件、生命周期）
├── core/
│   ├── config.py                    # 全局配置（pydantic-settings，支持 .env）
│   ├── cache.py                     # Redis 缓存层（优雅降级，所有函数 Redis 不可用时静默返回）
│   ├── logging.py                   # 结构化日志（structlog + correlation ID）
│   ├── tracing.py                   # OpenTelemetry 链路追踪（@traced 装饰器）
│   └── metrics.py                   # Prometheus 指标定义（评估/Agent/LLM/Sandbox/HTTP）
├── api/
│   ├── auth_middleware.py           # API Key 认证中间件
│   ├── rate_limit_middleware.py     # 接口限流中间件（Redis 滑动窗口）
│   ├── correlation_id_middleware.py # 请求关联 ID 中间件（全链路追踪）
│   └── metrics_middleware.py        # Prometheus HTTP 指标采集中间件
└── celery_app.py                    # Celery 异步任务配置（可选，优雅降级）
```

#### `main.py` — 应用入口

**功能**：创建 FastAPI 应用，注册所有路由和中间件。

**启动流程**（`lifespan`）：
1. `init_db()` — 初始化数据库
2. `init_redis()` — 连接 Redis（不可用时静默跳过）
3. `wiki_agent_startup()` — 初始化 Wiki Agent
5. `init_session_pool()` — 初始化 Agent 运行时会话池
6. `init_tracing()` — 初始化 OpenTelemetry

**中间件栈**（从外到内）：
```
CORS → PrometheusMetrics → CorrelationId → RateLimit → Auth → 路由处理
```

#### `core/config.py` — 全局配置

**功能**：使用 `pydantic_settings` 管理所有可配置参数。

**关键配置项**：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./agent_eval.db` | 数据库连接 |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis 连接 |
| `DEEPSEEK_API_KEY` | — | DeepSeek API 密钥 |
| `ZHIPUAI_API_KEY` | — | 智谱 GLM API 密钥 |
| `QWEN_API_KEY` | — | 通义千问 API 密钥 |
| `DEFAULT_LLM_PROVIDER` | `deepseek` | 默认 LLM 提供商 |
| `EVAL_DIMENSION_WEIGHTS` | 6 维权重 | 评估维度权重配置 |
| `AGENT_MAX_STEPS` | 20 | Agent 最大步数 |
| `AUTH_ENABLED` | `false` | 是否启用认证 |

#### `core/cache.py` — Redis 缓存层

**功能**：异步 Redis 缓存，所有函数在 Redis 不可用时静默返回 None/False。

**核心功能**：
- `cache_get()` / `cache_set()` — JSON 序列化的键值存取
- `cache_hgetall()` / `cache_hset()` — Hash 操作
- `cache_incr()` / `cache_lpush()` / `cache_lrange()` — 计数器和列表操作
- `cache_delete_pattern()` — 按模式批量删除（SCAN 游标）
- `check_rate_limit()` — 滑动窗口限流器（Sorted Set）
- `hash_prompt()` — SHA-256 哈希（用于 LLM 缓存键）

#### `core/logging.py` — 结构化日志

**功能**：基于 structlog 的结构化日志，自动注入 correlation_id。

**特性**：
- 生产环境：JSON 格式输出（ELK/Loki 兼容）
- 开发环境：彩色控制台输出
- 自动注入 `request_id`（correlation_id）
- 抑制第三方库噪音日志

#### `core/tracing.py` — OpenTelemetry 链路追踪

**功能**：初始化 OpenTelemetry TracerProvider，支持导出到 Jaeger/Collector。

**API**：
- `get_tracer(name)` — 获取命名 Tracer
- `@traced(name)` — 装饰器，自动包裹函数为 tracing span
- `is_tracing_active()` — 检查追踪是否激活

#### `core/metrics.py` — Prometheus 指标

**功能**：定义所有 Prometheus 指标。

**指标分类**：

| 类别 | 指标 | 说明 |
|------|------|------|
| 评估 | `EVALUATION_COUNT` / `EVALUATION_DURATION` / `EVALUATION_SCORE` | 评估次数、耗时、分数分布 |
| Agent | `AGENT_STEPS` / `AGENT_RUN_DURATION` | Agent 步数、运行耗时 |
| LLM | `LLM_CALL_COUNT` / `LLM_CALL_DURATION` / `LLM_TOKENS` | LLM 调用次数、延迟、Token 用量 |
| Tool | `TOOL_CALL_COUNT` / `TOOL_CALL_DURATION` | 工具调用次数、耗时 |
| HTTP | `HTTP_REQUEST_COUNT` / `HTTP_REQUEST_DURATION` | HTTP 请求次数、延迟 |

---

### 3.2 数据库与模型层

```
app/
├── db/
│   ├── database.py                  # SQLAlchemy 异步引擎 + 会话工厂
│   └── models.py                    # ORM 模型（AgentTask / AgentTrajectory / Evaluation / Workspace）
├── models/
│   ├── action_types.py              # 14 种轨迹动作类型常量
│   └── schemas.py                   # Pydantic 请求/响应模型
```

#### `db/models.py` — ORM 模型

**核心表**：

| 表 | 说明 | 关键字段 |
|----|------|---------|
| `agent_tasks` | Agent 任务 | id, workspace_id, goal, context, status, timestamps |
| `agent_trajectories` | 执行轨迹 | task_id, step_number, action_type, action_detail, observation |
| `evaluations` | 评估结果 | task_id, 6 维分数, 6 维反馈, prompt_version, model_name |
| `workspaces` | 工作空间 | id, name, description |

**状态枚举**：
- `TaskStatus`: pending → running → completed / failed / timeout
- `EvaluationStatus`: pending → in_progress → completed / failed

#### `models/action_types.py` — 动作类型

**14 种轨迹动作类型**：

| 类型 | 说明 |
|------|------|
| `plan` | 初始规划（milestones / steps） |
| `plan_update` | 动态规划更新 |
| `tool_call` | 工具调用 |
| `tool_result` | 工具返回 |
| `memory_write` / `memory_read` | 记忆读写 |
| `state_change` | 状态变化 |
| `think` | 思考过程 |
| `replan` | 重规划 |
| `failure` | 失败/异常 |
| `node_execute` | LangGraph 节点执行 |
| `tool_decision` | 工具选择决策 |
| `retrieval` | 知识库检索 |
| `evidence` | 证据池构建 |

#### `models/schemas.py` — Pydantic 模型

**主要模型**：

| 模型 | 说明 |
|------|------|
| `TaskCreate` / `TaskResponse` | 任务创建/响应 |
| `TrajectoryStep` / `TrajectoryCreate` | 轨迹步骤 |
| `EvaluationRequest` / `EvaluationResponse` | 评估请求/响应 |
| `OverallEvaluation` | 6 维综合评估结果 |
| `PlanningScore` / `TacticalScore` / `ToolUseScore` / `MemoryScore` / `ReplanScore` / `RetrievalScore` | 各维度评分 |
| `TrajectoryDiffResponse` / `StepDiff` | 轨迹 Diff |
| `ReplayResponse` / `LLMTraceInfo` | Replay 调试数据 |
| `JudgeRawData` | Judge 透明面板数据 |
| `RegressionReport` | 回归检测报告 |

---

### 3.3 评估引擎层

```
app/
├── evaluators/
│   ├── __init__.py                  # 导出 6 个评估器
│   ├── base.py                      # ★ 评估器基类（LLM 调用、缓存、JSON 解析、轨迹提取）
│   ├── planning_evaluator.py        # 规划质量评估器（覆盖率/顺序性/粒度/完整性）
│   ├── tactical_evaluator.py        # 战术决策评估器（相关性/效率/正确性）
│   ├── tool_use_evaluator.py        # 工具使用评估器（选择质量/参数准确性/结果利用）
│   ├── memory_evaluator.py          # 记忆保持评估器（保持力/相关性/一致性）
│   ├── replan_evaluator.py          # 重规划评估器（触发适当性/适应质量/失败中学习）
│   ├── retrieval_evaluator.py       # 检索质量评估器（相关性/证据准确性/覆盖度 + 幻觉检测）
│   ├── scoring.py                   # 评分工具（适用性判断、加权总分计算）
│   ├── consensus.py                 # 多模型共识引擎（跨厂商独立评分）
│   └── trajectory_compressor.py     # 轨迹压缩器（4 阶段管线，减少 Judge token 消耗）
├── graphs/
│   └── evaluation_graph.py          # ★ LangGraph 评估工作流（串行/并行/增量评估）
```

#### `evaluators/base.py` — 评估器基类

**功能**：所有评估器的抽象基类，提供通用能力。

**核心能力**：
- `_get_default_llm()` — 根据配置创建 LLM（支持 DeepSeek/OpenAI/Anthropic/GLM/Qwen）
- `_invoke_llm_cached()` — 带 Redis 缓存的 LLM 调用（按评估器名 + 模型名 + prompt hash 隔离缓存）
- `_parse_json_from_llm()` — 鲁棒的 JSON 提取（3 种策略：fenced code block → balanced braces → greedy fallback）
- `_format_trajectory()` — 轨迹格式化（支持 4 阶段压缩）
- `_extract_plans()` / `_extract_tool_calls()` / `_extract_replans()` / ... — 从轨迹提取特定类型步骤
- `get_last_judge_raw()` / `get_judge_raw_history()` — 获取 Judge 原始数据（透明面板）

#### 6 个评估器

| 评估器 | 维度 | 子指标 | 评估内容 |
|--------|------|--------|---------|
| `PlanningEvaluator` | 规划质量 (20%) | 覆盖率、顺序性、粒度、完整性 | 计划是否覆盖关键里程碑、顺序是否合理、粒度是否适当 |
| `TacticalEvaluator` | 战术决策 (20%) | 相关性、效率、正确性 | 每一步行动是否与目标相关、是否高效、是否正确 |
| `ToolUseEvaluator` | 工具使用 (15%) | 选择质量、参数准确性、结果利用 | 是否选对工具、参数是否正确、结果是否被有效利用 |
| `MemoryEvaluator` | 记忆保持 (15%) | 保持力、相关性、一致性 | 是否记住关键事实、回忆是否相关、记忆是否一致 |
| `ReplanEvaluator` | 重规划 (15%) | 触发适当性、适应质量、失败中学习 | 重规划时机是否恰当、新计划是否合理、是否从失败中学习 |
| `RetrievalEvaluator` | 检索质量 (15%) | 相关性、证据准确性、覆盖度 + 幻觉检测 | 检索文档是否相关、回答是否基于检索、是否有幻觉 |

**评估器工作流程**：
1. 从轨迹中提取相关步骤
2. 通过 `TrajectoryCompressor` 压缩轨迹（减少 token 消耗）
3. 构建评估 Prompt（中文）
4. 调用 LLM（带缓存）
5. 解析 JSON 响应
6. 返回结构化评分

#### `evaluators/scoring.py` — 评分工具

**功能**：计算加权总分，处理维度适用性。

- `is_applicable()` — 判断维度是否适用（如无工具调用时 Tool Use 标记为 N/A）
- `dimension_score()` — 提取维度分数
- `weighted_overall()` — 计算加权总分（不适用维度自动剔除，权重重新归一化）

#### `evaluators/consensus.py` — 多模型共识

**功能**：使用多个 LLM 独立评分，输出均值和标准差。

**共识策略**（优先级递减）：
1. **跨厂商共识**：DeepSeek + GLM + Qwen（最可靠）
2. **同厂商多模型**：deepseek-chat + deepseek-reasoner
3. **温度多样性**：同模型不同 temperature（兜底）

#### `evaluators/trajectory_compressor.py` — 轨迹压缩器

**功能**：4 阶段压缩管线，减少 LLM Judge 的 token 消耗。

| 阶段 | 说明 |
|------|------|
| ① Importance Filter | 保留高价值 action_type（plan/tool_call/memory/replan/retrieval/failure） |
| ② Think Summary | 长 think 步骤 observation 截断至 200 字符 |
| ③ Recent Window | 保留最近 30 步 + plan/failure 锚点 |
| ④ Context Builder | 格式化输出 |

#### `graphs/evaluation_graph.py` — 评估工作流

**功能**：LangGraph 编排的评估工作流。

**两种执行模式**：
1. **串行模式**（`create_evaluation_graph`）：validate → planning → tactical → tool_use → memory → replan → retrieval → aggregate
2. **并行模式**（`evaluate_parallel`）：6 个评估器通过 `asyncio.gather` 并发执行（71s → ~15s）

**部分评估**（`evaluate_partial`）：只运行指定维度的评估器（用于增量评估）。

---

### 3.4 服务层

```
app/
├── services/
│   ├── evaluation_service.py        # ★ 评估编排服务（创建评估、流式评测、SSE 推送）
│   ├── judge_service.py             # Judge 透明面板服务（提取原始 Prompt/Response）
│   ├── replay_service.py            # Replay 调试服务（步进式回放 LLM 调用）
│   ├── diff_service.py              # 轨迹 Diff 服务（步骤级对比两次运行）
│   ├── incremental_eval.py          # 增量评估服务（只重算受影响维度）
│   ├── regression_detection.py      # 回归检测服务（对比基线分数）
│   ├── system_health.py             # 系统健康检查
│   ├── quota.py                     # 配额管理
│   └── webhook.py                   # Webhook 通知
```

#### `evaluation_service.py` — 评估编排服务

**功能**：评估的完整生命周期管理。

**核心流程**：
1. 创建评估记录（`Evaluation`）
2. 获取轨迹数据（`AgentTrajectory`）
3. 运行 6 维评估（并行 `asyncio.gather`）
4. 计算加权总分
5. 持久化结果
6. 失效相关缓存

**SSE 流式评测**：
- 评估进度实时推送给前端
- 防重复执行（Redis 分布式锁 / 本地锁）

#### `judge_service.py` — Judge 透明面板

**功能**：提取每个维度的 LLM Judge 原始 Prompt 和 Response。

**返回数据**：
- `judge_prompt` — 发送给 Judge LLM 的完整 Prompt
- `judge_response` — Judge LLM 的原始响应
- `judge_model` — 使用的模型
- `score` — 最终分数
- `score_breakdown` — 子指标分数

#### `replay_service.py` — Replay 调试器

**功能**：步进式回放 Agent 的每一步执行。

**每步数据**：
- `step_number` — 步骤号
- `action_type` — 动作类型
- `llm_prompt` — LLM 原始 Prompt
- `llm_response` — LLM 原始 Response
- `llm_model` — 使用的模型
- `latency_ms` — 调用延迟

#### `diff_service.py` — 轨迹 Diff

**功能**：步骤级对比两次 Agent 运行的差异。

**Diff 类型**：
- `added` — 新增步骤
- `removed` — 删除步骤
- `changed` — 修改步骤（含字段级变化列表）
- `unchanged` — 未变化步骤

#### `incremental_eval.py` — 增量评估

**功能**：只重算受影响的评估维度，复用未变化维度的分数。

**变化-维度映射**：

| 变化类型 | 受影响维度 |
|---------|-----------|
| prompt / plan 变化 | planning, tactical |
| 工具变化 | tool_use |
| 检索配置变化 | retrieval |
| 记忆配置变化 | memory, replan |

#### `regression_detection.py` — 回归检测

**功能**：对比两次评估的分数，检测退化维度。

**阈值配置**：

| 维度 | 默认阈值 |
|------|---------|
| overall | -5.0 |
| planning / tactical / memory / replan / retrieval | -10.0 |
| tool_use | -8.0 |

---

### 3.5 Agent 运行时层

```
app/
├── agent_runtime/
│   ├── graph.py                     # ★ LangGraph ReAct Agent 循环（think → act → loop）
│   ├── state.py                     # Agent 状态定义（AgentState TypedDict）
│   ├── trajectory_recorder.py       # 轨迹记录器（14 种动作类型）
│   ├── llm_factory.py               # LLM 工厂（根据 provider 创建 LLM 实例）
│   ├── mock_executor.py             # Mock 执行器（无需 Docker 的模拟轨迹）
│   ├── prompts/                     # Agent 系统 Prompt
│   │   └── __init__.py              # Prompt 模板 + 版本管理
│   ├── tools/                       # Agent 工具集
│   │   ├── bash_execute.py          # Bash 执行工具
│   │   ├── python_execute.py        # Python 执行工具
│   │   ├── file_read.py             # 文件读取工具
│   │   ├── file_write.py            # 文件写入工具
│   │   └── file_list.py             # 文件列表工具
│       ├── executor.py              # SandboxExecutor（一次性代码执行）
│       ├── session_pool.py          # SessionPool（可复用容器会话池）
│       ├── workspace.py             # WorkspaceManager（工作区文件管理）
│       ├── detector.py              # 代码片段检测器
│       └── models.py                # 沙箱数据模型
```


**功能**：基于 LangGraph 的 Agent ReAct 循环。

**流程**：`START → think_and_act → (done? → END : → think_and_act)`

**`think_and_act` 节点**：
1. 检查是否达到最大步数
2. 构建消息列表（SystemPrompt + ChatHistory + FinalAnswerInstruction）
3. 调用 LLM（带工具绑定）
4. 如果 LLM 返回工具调用 → 执行工具 → 记录轨迹 → 继续循环
5. 如果 LLM 返回最终答案 → 记录轨迹 → 结束


**功能**：Agent 运行的顶层编排器。

**完整流程**：
2. 获取沙箱会话（`SessionPool`）
3. 初始化工作区（`WorkspaceManager`，写入初始文件）
4. 创建 LLM（`llm_factory`）
5. 创建 Agent Graph（`create_agent_graph`）
6. 运行 Agent 循环
7. 捕获工作区最终状态
8. 清理会话


**功能**：将 Agent 运行时事件映射为 `TrajectoryStep` 记录。

**记录方法**：

| 方法 | 动作类型 | 说明 |
|------|---------|------|
| `record_plan()` | plan | 初始规划 |
| `record_think()` | think | 思考过程（含 LLM trace） |
| `record_tool_call()` | tool_call + tool_result | 工具调用和结果 |
| `record_replan()` | replan | 重规划 |
| `record_failure()` | failure | 失败事件 |
| `record_state_change()` | state_change | 状态变化 |
| `record_node_execute()` | node_execute | LangGraph 节点执行 |



**调用链**：
1. 验证（工具是否在允许列表中）
2. 审计日志
3. 在沙箱容器中执行（带超时）
4. 记录轨迹（tool_call + tool_result）

---

### 3.6 SDK 轨迹采集层

```
sdk/
├── __init__.py                      # SDK 入口（导出三种适配器 + Collector）
├── collector.py                     # ★ 轨迹收集器（线程安全、批量上传、指数退避重试）
└── adapters/
    ├── langgraph.py                 # LangGraph 适配器（一行替换自动采集）
    ├── llm_proxy.py                 # LLM Proxy 适配器（代理 LLM 调用自动采集）
    └── callback.py                  # LangChain Callback 适配器
```

#### `sdk/collector.py` — 轨迹收集器

**功能**：轻量级轨迹收集器，零外部依赖。

**特性**：
- 线程安全（`threading.Lock`）
- 批量上传 + 失败回退缓冲 + 指数退避重试
- 离线模式：不配置 `EVAL_API_BASE_URL` 时纯内存缓冲
- 支持全部 14 种轨迹动作类型
- 单例模式 + `reset()` / `close()` 生命周期管理

**API**：
- `start(goal, context)` — 开始采集会话，返回 task_id
- `record(action_type, detail)` — 记录一个轨迹步骤
- `finish(auto_run)` — 结束采集，flush 轨迹，可选触发评估
- `record_retrieval()` / `record_memory_write()` — 语义化记录方法

#### `sdk/adapters/langgraph.py` — LangGraph 适配器

**功能**：一行替换，自动采集 LangGraph 执行轨迹。

**使用方式**：
```python
# 原来的代码
graph = build_graph()

# 替换为
graph = instrument_langgraph(build_graph())

# 后续使用完全相同
result = await graph.ainvoke(initial_state)
```

**自动采集**：
- 节点执行（node_execute）
- 状态变化（state_change）— 节点执行前后自动记录 diff
- 工具调用（tool_call）/ 工具决策（tool_decision）
- 失败事件（failure）

#### `sdk/adapters/llm_proxy.py` — LLM Proxy 适配器

**功能**：代理 LLM 调用，自动采集 Prompt/Response/Latency。

**使用方式**：
```python
llm = create_proxy_llm(original_llm)
# 后续使用完全相同
response = await llm.ainvoke(messages)
```

#### `sdk/adapters/callback.py` — Callback 适配器

**功能**：LangChain Callback Handler，最轻量的集成方式。

**使用方式**：
```python
handler = create_callback_handler()
llm = ChatZhipuAI(callbacks=[handler])
```

---

### 3.7 API 路由层

```
app/
├── api/
│   └── v1/
│       └── endpoints/
│           ├── tasks.py             # 任务 API（CRUD、轨迹提交）
│           ├── evaluation.py        # ★ 评估 API（创建、运行、流式、共识、增量、批量）
│           ├── reports.py           # 报告 API（评分摘要、趋势、维度统计、迭代对比）
│           ├── benchmark.py         # 基准测试 API（单调性测试）
│           ├── system.py            # 系统 API（健康检查、Prometheus 指标）
│           ├── settings.py          # 设置 API
│           └── workspace.py         # 工作空间 API
```

#### `evaluation.py` — 评估 API

**功能**：评估的完整 API 接口。

**主要端点**：

| 端点 | 说明 |
|------|------|
| `POST /run` | 创建并运行评估（Sandbox 模式） |
| `POST /stream` | SSE 流式评估 |
| `POST /consensus` | 多模型共识评估 |
| `POST /incremental` | 增量评估 |
| `POST /batch` | 批量评估 |
| `GET /{id}` | 获取评估详情 |
| `GET /{id}/replay` | 获取 Replay 数据 |
| `GET /{id}/judge-raw` | 获取 Judge 透明面板数据 |
| `POST /compare` | 对比两次评估（回归检测） |
| `POST /diff` | 轨迹 Diff |

#### `tasks.py` — 任务 API

**功能**：任务管理和轨迹提交。

| 端点 | 说明 |
|------|------|
| `POST /` | 创建任务 |
| `GET /` | 列出任务（支持 workspace 过滤） |
| `GET /{id}` | 获取任务详情 |
| `POST /{id}/trajectory` | 提交轨迹 |
| `GET /{id}/trajectory` | 获取轨迹 |

#### `reports.py` — 报告 API

**功能**：评分报告和趋势分析。

| 端点 | 说明 |
|------|------|
| `GET /summary` | 评分摘要 |
| `GET /trends` | 趋势分析 |
| `GET /dimensions` | 维度统计 |
| `GET /iterations` | 迭代对比 |

---

### 3.8 前端层

```
frontend/src/
├── main.ts                          # Vue 应用入口
├── App.vue                          # 根组件
├── router/index.ts                  # 路由配置
├── api/index.ts                     # API 客户端（axios）
├── layouts/
│   └── MainLayout.vue               # 主布局（侧边栏 + 内容区）
├── views/
│   ├── Dashboard.vue                # ★ 仪表盘（任务统计、评分分布、趋势图）
│   ├── Tasks.vue                    # 任务列表
│   ├── TaskDetail.vue               # 任务详情
│   ├── Evaluations.vue              # 评估列表
│   ├── EvaluationDetail.vue         # ★ 评估详情（6 维雷达图、打分明细、Judge 透明面板）
│   ├── Analytics.vue                # 分析报告（趋势、维度统计）
│   ├── Benchmark.vue                # 基准测试
│   ├── Settings.vue                 # 系统设置
│   ├── SystemInspector.vue          # 系统检查器
│   ├── VectorAdmin.vue              # 向量管理
│   └── WikiAgent.vue                # Wiki Agent 入口
├── utils/
│   ├── evaluationStream.ts          # SSE 流式评估工具
│   └── reportCharts.ts              # ECharts 图表配置
└── wiki/                            # Wiki Agent 前端（详见 wiki-agent 文档）
    ├── WikiAgentApp.vue
    └── components/
```

#### `Dashboard.vue` — 仪表盘

**功能**：评估平台的主页仪表盘。

**展示内容**：
- 任务统计（总数、状态分布）
- 评分分布直方图
- 评分趋势折线图
- 最近评估列表

#### `EvaluationDetail.vue` — 评估详情

**功能**：单次评估的详细展示。

**展示内容**：
- 6 维雷达图
- 各维度分数和反馈
- Judge 透明面板（原始 Prompt/Response）
- 轨迹时间线
- 多模型对比（共识模式）
- 回归检测结果

---

### 3.9 基准测试与脚本

```
scripts/
├── benchmark_evaluators.py          # 评估器基准测试
├── benchmark_multimodel.py          # 多模型共识基准测试
├── benchmark_score_distribution.py  # 分数分布基准测试
├── eval_evaluator_accuracy.py       # 评估器准确率评估
├── eval_query_rewrite_ab.py         # Query 改写 A/B 测试
├── eval_retrieval_standalone.py     # 检索质量独立评估
├── generate_interview_answers.py    # 面试题答案生成
└── interview_answer_bank.py         # 面试题答案库
```

---

### 3.10 测试套件

```
tests/
├── conftest.py                      # 测试配置
├── test_evaluators.py               # 评估器测试
├── test_golden_suite.py             # ★ Golden Test Suite（4 条黄金轨迹 + 预期分数范围）
├── test_evaluation_service.py       # 评估服务测试
├── test_incremental_eval.py         # 增量评估测试
├── test_regression_detection.py     # 回归检测测试
├── test_diff_service.py             # Diff 服务测试
├── test_judge_service.py            # Judge 服务测试
├── test_replay_service.py           # Replay 服务测试
├── test_api.py                      # API 测试
├── test_vector_store.py             # 向量存储测试
├── test_vector_admin.py             # 向量管理测试
├── test_search_rerank.py            # 搜索重排测试
├── test_wiki_plan_rerank.py         # Wiki 计划重排测试
└── ...                              # 更多测试
```

---

## 四、架构设计

### 4.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Frontend (Vue 3 + Element Plus)                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │Dashboard │  │Evaluations│  │ Analytics│  │  Tasks   │  │WikiAgent │ │
│  │ 仪表盘   │  │ 评估详情  │  │ 趋势分析 │  │ 任务管理 │  │ 知识库   │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘ │
└───────┼──────────────┼──────────────┼──────────────┼──────────────┼─────┘
        │ SSE          │ REST         │ REST         │ REST         │ REST
        ▼              ▼              ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    FastAPI + Middleware Stack                            │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ CORS → Prometheus → CorrelationId → RateLimit → Auth → Router   │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  API Endpoints                                                   │  │
│  │  /api/v1/evaluations  /api/v1/tasks  /api/v1/reports            │  │
│  │  /api/v1/benchmark    /api/v1/system /api/v1/settings           │  │
│  │  /api/wiki            /api/chat      /api/debug                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
┌──────────────────┐ ┌──────────────┐ ┌──────────────────┐
│  评估引擎         │ │ Agent Runtime│ │  Wiki Agent      │
│                  │ │              │ │                  │
│ ┌──────────────┐ │ │ ┌──────────┐ │ │ ┌──────────────┐ │
│ │ 评估工作流    │ │ │ │ LangGraph│ │ │ │ 对话编排      │ │
│ │ (LangGraph)  │ │ │ │ ReAct    │ │ │ │ (LangGraph)  │ │
│ └──────┬───────┘ │ │ └──────────┘ │ │ └──────────────┘ │
│        │         │ │ ┌──────────┐ │ │ ┌──────────────┐ │
│ ┌──────┴───────┐ │ │ │ Sandbox  │ │ │ │ 混合检索      │ │
│ │ 6 评估器     │ │ │ │ Session  │ │ │ │ Milvus+BM25  │ │
│ │ (并行)       │ │ │ │ Pool     │ │ │ │ +Reranker    │ │
│ └──────────────┘ │ │ └──────────┘ │ │ └──────────────┘ │
│ ┌──────────────┐ │ │ ┌──────────┐ │ │ ┌──────────────┐ │
│ │ 共识评估     │ │ │ │ 工具集   │ │ │ │ 四端同步      │ │
│ │ 增量评估     │ │ │ │ 5 tools  │ │ │ │ SyncManager  │ │
│ │ 回归检测     │ │ │ └──────────┘ │ │ └──────────────┘ │
│ └──────────────┘ │ └──────────────┘ └──────────────────┘
└──────────────────┘
              │              │              │
              ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Storage Layer 存储层                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │ SQLite/  │  │  Redis   │  │ Milvus   │  │ 文件系统 │  │   Git    │ │
│  │ Postgres │  │  缓存    │  │ 向量DB   │  │ Markdown │  │ 版本控制 │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
              ▲
              │
┌─────────────┴───────────────────────────────────────────────────────────┐
│                    SDK 轨迹采集层                                        │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐      │
│  │ LangGraph Adapter│  │  LLM Proxy       │  │  Callback Handler│      │
│  │ 一行替换自动采集  │  │ 代理LLM调用采集  │  │ 最轻量集成方式   │      │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘      │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  TrajectoryCollector — 批量上传 + 失败回退 + 指数退避重试        │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### 4.2 评估工作流图

```
评估请求
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│  EvaluationService.create_evaluation()                      │
│  ① 创建 Evaluation 记录（IN_PROGRESS）                      │
│  ② 获取轨迹数据（AgentTrajectory）                          │
│  ③ 转换为 TrajectoryStep 列表                               │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  evaluate_parallel() — 6 个评估器通过 asyncio.gather 并发    │
│                                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                    │
│  │ Planning │ │ Tactical │ │ ToolUse  │                    │
│  │ 评估器   │ │ 评估器   │ │ 评估器   │                    │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘                    │
│       │            │            │                           │
│  ┌────┴─────┐ ┌────┴─────┐ ┌────┴─────┐                    │
│  │ Memory   │ │ Replan   │ │ Retrieval│                    │
│  │ 评估器   │ │ 评估器   │ │ 评估器   │                    │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘                    │
│       │            │            │                           │
│       └────────────┼────────────┘                           │
│                    │                                        │
│  每个评估器内部:                                              │
│  ① TrajectoryCompressor 压缩轨迹                            │
│  ② 构建评估 Prompt（中文）                                   │
│  ③ _invoke_llm_cached()（Redis 缓存 + Judge Raw 记录）      │
│  ④ _parse_json_from_llm() 解析 JSON                        │
│  ⑤ 返回结构化评分                                           │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  聚合结果                                                    │
│  ① score_values() — 提取各维度分数                           │
│  ② weighted_overall() — 加权总分（不适用维度自动剔除）        │
│  ③ _generate_summary() — 生成中文摘要                       │
│  ④ _generate_recommendations() — 生成改进建议               │
│  ⑤ 持久化到 Evaluation 表                                    │
│  ⑥ 失效相关 Redis 缓存                                      │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
              评估完成（COMPLETED）
```

---

### 4.3 Agent 运行时流程图

```
评估请求（Sandbox 模式）
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│  ① Mock 模式检查 → 返回预定义轨迹                            │
│  ② SessionPool.acquire() → 获取 Docker 容器                 │
│  ③ WorkspaceManager.setup() → 写入初始文件到 /workspace      │
│  ④ llm_factory.create_llm() → 创建 LLM 实例                │
│  ⑤ create_agent_graph() → 构建 LangGraph Agent              │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  LangGraph ReAct 循环                                        │
│                                                             │
│  START → think_and_act → (done? → END : → think_and_act)   │
│                                                             │
│  think_and_act 节点:                                        │
│  ① 检查是否达到最大步数                                      │
│  ② 构建消息列表（SystemPrompt + History + FinalAnswer）      │
│  ③ LLM.bind_tools() → 调用 LLM                             │
│  ④ 如果 LLM 返回工具调用:                                    │
│     ├─ TrajectoryCollector.record_tool_call() → 记录轨迹      │
│     └─ 将结果加入消息列表 → 继续循环                         │
│  ⑤ 如果 LLM 返回最终答案:                                    │
│     ├─ TrajectoryCollector.record_think() → 记录轨迹          │
│     └─ done=True → 结束                                     │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  收尾                                                        │
│  ① WorkspaceManager.capture() → 捕获工作区最终状态           │
│  ② SessionPool.release() → 释放容器                         │
│     - trajectory: 完整轨迹                                   │
│     - final_answer: Agent 最终回答                           │
│     - workspace_state: 工作区状态                            │
│     - steps_taken / duration_ms                              │
└─────────────────────────────────────────────────────────────┘
```

---

### 4.4 SDK 轨迹采集架构

```
Agent 项目（Wiki Agent / 外部 Agent）
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│  SDK 集成（三种方式任选其一）                                  │
│                                                             │
│  方式 1: LangGraph Adapter                                   │
│  graph = instrument_langgraph(build_graph())                │
│  → 自动采集: node_execute, state_change, tool_call, failure │
│                                                             │
│  方式 2: LLM Proxy                                           │
│  llm = create_proxy_llm(original_llm)                       │
│  → 自动采集: LLM prompt/response/latency                    │
│                                                             │
│  方式 3: Callback Handler                                     │
│  handler = create_callback_handler()                        │
│  llm = ChatZhipuAI(callbacks=[handler])                     │
│  → 自动采集: LLM 调用事件                                    │
│                                                             │
│  方式 4: 手动记录（任意框架）                                  │
│  collector.record_retrieval(query, results, ms)             │
│  → 灵活记录任意操作                                          │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  TrajectoryCollector（单例）                                 │
│                                                             │
│  ① start(goal, context) → 创建 task_id                     │
│  ② record(action_type, detail) → 追加到内存缓冲             │
│  ③ finish(auto_run) → HTTP flush 到平台                     │
│                                                             │
│  传输层:                                                     │
│  - HTTP: POST /api/v1/tasks/{id}/trajectory（批量上传）      │
│  - 异步: asyncio.to_thread 不阻塞事件循环                    │
│  - 失败回退: 内存缓冲 + 指数退避重试                         │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  评估平台接收                                                │
│  ① 持久化轨迹到 agent_trajectories 表                       │
│  ② 触发评估（可选 auto_run）                                 │
│  ③ 6 维评估 → 返回评估结果                                   │
└─────────────────────────────────────────────────────────────┘
```

---

### 4.5 6 维评估体系

```
                    ┌─────────────────────┐
                    │   Overall Score     │
                    │   加权总分 0-100     │
                    └──────────┬──────────┘
                               │
        ┌──────────┬───────────┼───────────┬──────────┬──────────┐
        ▼          ▼           ▼           ▼          ▼          ▼
┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐
│Planning  ││Tactical  ││Tool Use  ││ Memory   ││ Replan   ││Retrieval │
│ 规划质量 ││ 战术决策 ││ 工具使用 ││ 记忆保持 ││ 重规划   ││ 检索质量 │
│ 20%      ││ 20%      ││ 15%      ││ 15%      ││ 15%      ││ 15%      │
└────┬─────┘└────┬─────┘└────┬─────┘└────┬─────┘└────┬─────┘└────┬─────┘
     │           │           │           │           │           │
     ▼           ▼           ▼           ▼           ▼           ▼
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│Coverage │ │Relevance│ │Selection│ │Retention│ │Trigger  │ │Relevance│
│顺序性   │ │效率     │ │参数准确 │ │相关性   │ │适应质量 │ │证据准确 │
│粒度     │ │正确性   │ │结果利用 │ │一致性   │ │失败学习 │ │覆盖度   │
│完整性   │ │         │ │         │ │         │ │         │ │幻觉检测 │
└─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘

质量等级：
  优秀 ≥ 80  ·  良好 ≥ 60  ·  一般 ≥ 40  ·  较差 < 40

适用性标记：
  维度不适用时自动标记为 N/A，从加权总分中剔除
  （如无工具调用时 Tool Use 标记为 N/A）
```

---

### 4.6 增量评估与回归检测

```
基线评估 (main branch)              新评估 (feature branch)
     │                                    │
     ▼                                    ▼
┌──────────────┐                    ┌──────────────┐
│ Evaluation A │                    │ Evaluation B │
│ planning: 80 │                    │ planning: 75 │
│ tactical: 70 │                    │ tactical: 85 │
│ tool_use: 60 │                    │ tool_use: 55 │
│ memory: 75   │                    │ memory: 75   │
│ replan: 65   │                    │ replan: 65   │
│ retrieval: 80│                    │ retrieval: 80│
│ overall: 72  │                    │ overall: 73  │
└──────┬───────┘                    └──────┬───────┘
       │                                   │
       └─────────────┬─────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  DiffService.compare()                                      │
│  步骤级对比两次轨迹差异                                       │
│  → TrajectoryDiffResponse (added/removed/changed/unchanged) │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  IncrementalEvalService                                     │
│  ① _detect_changed_dimensions() → 检测受影响维度            │
│  ② evaluate_partial() → 只重算受影响维度                    │
│  ③ 复用未变化维度的分数                                      │
│  ④ 计算新的加权总分                                          │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  RegressionDetectionService                                 │
│  对比各维度分数与阈值:                                       │
│                                                             │
│  planning: 80→75 (-5.0)  阈值 -10.0  ✅ 无回归              │
│  tactical: 70→85 (+15.0) 阈值 -10.0  ✅ 改进               │
│  tool_use: 60→55 (-5.0)  阈值 -8.0   ✅ 无回归              │
│  memory:   75→75 (0.0)   阈值 -10.0  ✅ 无变化              │
│  replan:   65→65 (0.0)   阈值 -10.0  ✅ 无变化              │
│  retrieval:80→80 (0.0)   阈值 -10.0  ✅ 无变化              │
│  overall:  72→73 (+1.0)  阈值 -5.0   ✅ 无回归              │
│                                                             │
│  → RegressionReport(has_regression=False)                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 五、数据流


```
用户请求 POST /api/v1/evaluations/run
     │
     ▼
evaluation_service.create_evaluation()
  ① 创建 AgentTask 记录
  ② 创建 Evaluation 记录 (IN_PROGRESS)
  ③ 启动后台任务
     │
     ▼
  ① SessionPool.acquire() → 获取 Docker 容器
  ② WorkspaceManager.setup() → 写入初始文件
  ③ create_agent_graph() → 构建 LangGraph
  ④ graph.ainvoke() → 运行 Agent ReAct 循环
     │
     ├─ think → TrajectoryCollector.record_think()
     ├─ replan → TrajectoryCollector.record_replan()
     └─ done → TrajectoryCollector.get_trajectory()
     │
     ▼
  ⑤ 持久化轨迹到 agent_trajectories 表
  ⑥ 释放沙箱会话
     │
     ▼
evaluate_parallel()
  ① 6 个评估器并行执行
  ② 每个评估器: 压缩轨迹 → 构建 Prompt → LLM 调用 → 解析结果
  ③ 加权总分计算
     │
     ▼
  ④ 持久化评估结果
  ⑤ 更新任务状态 (COMPLETED)
  ⑥ 返回评估结果
```

### 5.2 SDK 埋点模式数据流

```
外部 Agent 项目
  collector = get_collector()
  task_id = collector.start("分析项目依赖")
     │
     ▼
Agent 执行过程中:
  collector.record_plan(steps=[...])
  collector.record_tool_call(name="bash", input="pip list", output="...")
  collector.record_think("分析依赖关系...")
  collector.record_replan(reason="...", new_plan={...})
     │
     ▼
collector.finish(auto_run=True)
  ① POST /api/v1/tasks/{id}/trajectory → 批量上传轨迹
  ② 创建 Evaluation 记录
  ③ 触发 6 维评估
     │
     ▼
  评估结果通过 API 返回
```

### 5.3 评估引擎数据流

```
TrajectoryStep 列表
     │
     ▼
TrajectoryCompressor.compress()
  ① Importance Filter — 保留高价值 action_type
  ② Think Summary — 截断长 think 步骤
  ③ Recent Window — 保留最近 30 步 + 锚点
  ④ Context Builder — 格式化输出
     │
     ▼
评估 Prompt 构建
  [System: 你是评估专家...]
  [User: 目标: {goal}]
  [User: 轨迹: {compressed_trajectory}]
  [User: 上下文: {context}]
  [User: 输出 JSON 格式...]
     │
     ▼
_invoke_llm_cached()
  ① 构建 cache_key = hash(evaluator + model + prompt)
  ② Redis GET → 命中则返回缓存
  ③ 未命中 → chain.ainvoke() → LLM 调用
  ④ 记录 Judge Raw 数据（透明面板）
  ⑤ Redis SET → 缓存结果
     │
     ▼
_parse_json_from_llm()
  ① 提取 fenced code block 中的 JSON
  ② 平衡大括号提取
  ③ Greedy fallback
     │
     ▼
结构化评分结果
  { coverage: 85, ordering: 70, granularity: 80, completeness: 75,
    overall: 78, feedback: "...", suggestions: [...] }
```

### 5.4 SSE 流式评测数据流

```
客户端 POST /api/v1/evaluations/stream
  { task_id }
     │
     ▼
StreamingResponse (text/event-stream)
     │
     ├─ data: {"type": "status", "message": "开始评估..."}
     │
     ├─ data: {"type": "dimension", "dimension": "planning", "score": 78}
     ├─ data: {"type": "dimension", "dimension": "tactical", "score": 85}
     ├─ data: {"type": "dimension", "dimension": "tool_use", "score": 70}
     ├─ data: {"type": "dimension", "dimension": "memory", "score": 82}
     ├─ data: {"type": "dimension", "dimension": "replan", "score": 65}
     ├─ data: {"type": "dimension", "dimension": "retrieval", "score": 90}
     │
     ├─ data: {"type": "overall", "score": 78.3}
     │
     └─ data: {"type": "done", "evaluation_id": "..."}
```

---

## 六、API 接口一览

### 评估 API (`/api/v1/evaluations`)

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/run` | 创建并运行评估 |
| POST | `/stream` | SSE 流式评估 |
| POST | `/consensus` | 多模型共识评估 |
| POST | `/incremental` | 增量评估 |
| POST | `/batch` | 批量评估 |
| GET | `/{id}` | 获取评估详情 |
| GET | `/{id}/replay` | 获取 Replay 数据 |
| GET | `/{id}/judge-raw` | 获取 Judge 透明面板 |
| POST | `/compare` | 回归检测 |
| POST | `/diff` | 轨迹 Diff |
| GET | `/` | 列出评估 |
| DELETE | `/{id}` | 删除评估 |

### 任务 API (`/api/v1/tasks`)

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/` | 创建任务 |
| GET | `/` | 列出任务 |
| GET | `/{id}` | 获取任务详情 |
| PUT | `/{id}` | 更新任务 |
| DELETE | `/{id}` | 删除任务 |
| POST | `/{id}/trajectory` | 提交轨迹 |
| GET | `/{id}/trajectory` | 获取轨迹 |

### 报告 API (`/api/v1/reports`)

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/summary` | 评分摘要 |
| GET | `/trends` | 趋势分析 |
| GET | `/dimensions` | 维度统计 |
| GET | `/iterations` | 迭代对比 |

### 系统 API (`/api/v1/system`)

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/config` | 配置查看 |
| GET | `/metrics` | Prometheus 指标 |

### 基准测试 API (`/api/v1/benchmark`)

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/monotonicity` | 单调性基准测试 |

---

## 七、关键设计决策

### 7.1 为什么用 LLM-as-Judge？

- **可扩展**：不需要人工标注数据，只需设计评估 Prompt
- **可解释**：每个分数都有 Judge 的详细反馈和推理过程
- **多维度**：6 个独立评估器，每个专注于一个维度
- **可校准**：Golden Test Suite 确保评估器修改不引入回归

### 7.2 为什么用多模型共识？

- **单一模型偏见**：不同 LLM 对同一轨迹的评分可能差异较大
- **跨厂商共识**：DeepSeek + GLM + Qwen 独立评分，取均值
- **置信度**：标准差越小 = 一致性越高 = 评分越可信
- **降级策略**：只有 1 个 API Key 时自动切换为温度多样性共识

### 7.3 为什么用增量评估？

- **成本节约**：只重算受影响维度，节省约 2/3 时间和 Token
- **变化检测**：Trajectory Diff 精确识别哪些步骤发生了变化
- **维度映射**：变化类型 → 受影响维度的映射关系
- **分数复用**：未变化维度直接复用基线评估的分数

### 7.4 为什么用 SDK 三种集成方式？

- **LangGraph Adapter**：最深度集成，自动采集节点执行/状态变化/工具调用
- **LLM Proxy**：中度集成，代理 LLM 调用采集 Prompt/Response
- **Callback Handler**：最轻量集成，仅需添加一个 callback

三种方式可以组合使用，覆盖不同粒度的采集需求。

### 7.5 为什么用轨迹压缩？

- **Token 限制**：LLM Judge 的上下文窗口有限
- **成本控制**：减少 Token 消耗 = 减少 API 费用
- **质量保持**：4 阶段压缩保留高价值步骤，丢弃低价值噪音
- **可配置**：Recent Window 大小可调

### 7.6 优雅降级策略

| 组件 | 不可用时的行为 |
|------|--------------|
| Redis | 所有缓存函数静默返回 None/False，无缓存直接读写数据库 |
| Docker | Mock 模式返回预定义轨迹 |
| Celery | 同步执行评估任务 |
| OpenTelemetry | 所有 tracing 变为 no-op |
| 多模型 | 单模型 + 温度多样性共识 |

---

# 评估平台数据采集架构 — 完整技术文档

> 本文档详细说明评估平台如何获取数据、获取哪些数据、为什么能获取、以及数据如何被消费。

---

## 目录

- [一、数据采集全景图](#一数据采集全景图)
- [二、两条数据采集路径](#二两条数据采集路径)
- [三、14 种轨迹数据类型详解](#三14-种轨迹数据类型详解)
- [四、核心代码逐行解析](#四核心代码逐行解析)
- [五、数据消费：6 个评估器](#五数据消费6-个评估器)
- [六、数据库表结构](#六数据库表结构)
- [七、为什么能获取到数据](#七为什么能获取到数据)

---

## 一、数据采集全景图

```
                    ┌─────────────────────────────────────────────┐
                    │              评估平台 (FastAPI)              │
                    │                                             │
                    │   ┌─────────────────────────────────────┐  │
                    │   │  REST API                            │  │
                    │   │  POST /tasks/                        │  │
                    │   │  POST /tasks/{id}/trajectory         │  │
                    │   │  POST /evaluations/                  │  │
                    │   └──────────────┬──────────────────────┘  │
                    │                  │                          │
                    │                  ▼                          │
                    │   ┌─────────────────────────────────────┐  │
                    │   │       EvaluationService              │  │
                    │   │  add_trajectory() → DB 写入          │  │
                    │   │  run_evaluation() → 6 个评估器并行    │  │
                    │   └─────────────────────────────────────┘  │
                    └──────────────────▲──────────────────────────┘
                                       │ HTTP
                         ┌─────────────┴─────────────┐
                         │                           │
          ┌──────────────┴──────┐      ┌─────────────┴─────────┐
          │  SDK 采集（所有 Agent 统一）  │
          │                             │
          │  Wiki Agent                 │
          │  外部 Agent                 │
          └─────────────────────────────┘
```

**统一为 SDK 单路径**：所有 Agent 通过 SDK HTTP 模式推送轨迹数据到评估平台。

---

## 二、两条数据采集路径

### 路径 1: SDK 采集（HTTP 模式）

**适用场景**：所有 Agent（Wiki Agent、外部 Agent、手动提交）统一使用此路径。

**工作原理**：Agent 代码调用 `collector.record_*()`，数据先缓冲到内存，`finish()` 时批量 HTTP POST 到评估平台。

**代码流程**：

```
Agent 代码
  │
  ├─ collector.start(goal, context)                    # sdk/collector.py:383
  │    ├─ 生成 UUID task_id
  │    ├─ POST /api/v1/tasks/                          # 创建评估任务
  │    └─ record(PLAN, {goal, context})                # 自动记录初始计划
  │
  ├─ collector.record_retrieval(query, results, ms)    # sdk/collector.py:874
  │    └─ record(RETRIEVAL, {...})                     # 追加到内存缓冲
  │
  ├─ collector.record_tool_call(name, input, output)   # sdk/collector.py:650
  │    └─ record(TOOL_CALL, {...})                     # 追加到内存缓冲
  │
  ├─ collector.record_think("分析结果")                 # sdk/collector.py:699
  │    └─ record(THINK, {thought})                     # 追加到内存缓冲
  │
  └─ collector.finish(auto_run=True)                   # sdk/collector.py:448
       ├─ record(THINK, "Run finished")
       ├─ _flush(block=True)                           # 批量上传
       │    └─ POST /api/v1/tasks/{id}/trajectory      # 发送所有缓冲步骤
       ├─ PUT /api/v1/tasks/{id}  status=completed     # 标记任务完成
       └─ POST /api/v1/evaluations/                    # 触发评估
```

**关键代码** (`sdk/collector.py:561-629`)：

```python
def record(self, action_type, action_detail, observation=None, *, dedupe_key=None):
    """核心记录方法 — 所有便捷方法的底层实现。"""
    session = self._session()
    if not session.task_id or not self._enabled:
        return None

    # 去重检查
    if dedupe_key:
        key = f"{action_type}:{dedupe_key}"
        if key in session.seen_events:
            return None
        session.seen_events.add(key)

    # 构建步骤
    with self._buffer_lock:
        session.step_counter += 1
        step = {
            "step_number": session.step_counter,
            "action_type": action_type,
            "action_detail": _short(action_detail),    # 截断到 4000 字符
            "observation": _observation_text(observation),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        session.steps.append(step)

        # 缓冲区满时自动 flush
        if len(session.steps) >= self._batch_size:
            threading.Thread(target=self._flush_steps, ...).start()

        return step
```

---

## 三、14 种轨迹数据类型详解

### 3.1 规划类

| ActionType | 记录方法 | 数据格式 | 示例 |
|-----------|---------|---------|------|
| `PLAN` | `start()` 自动记录 | `{goal, context}` | `{"goal": "实现登录", "context": {"key_facts": [...]}}` |
| `PLAN_UPDATE` | `record_plan_update()` | `{milestone_status, next_action, reason, remaining_steps}` | `{"milestone_status": {"step1": "done"}, "next_action": "实现注册"}` |
| `REPLAN` | `record_replan()` | `{reason, new_plan, trigger}` | `{"reason": "JWT 库不兼容", "new_plan": "升级到 v2.0"}` |

### 3.2 工具类

| ActionType | 记录方法 | 数据格式 | 示例 |
|-----------|---------|---------|------|
| `TOOL_CALL` | `record_tool_call()` | `{tool_name, input, duration_ms}` + observation=output | `{"tool_name": "python_execute", "input": {"code": "print(1)"}}` |
| `TOOL_RESULT` | `record_tool_result()` | `{tool_name, success, error_type, duration_ms}` + observation=output | `{"tool_name": "python_execute", "success": true}` |
| `TOOL_DECISION` | `record(TOOL_DECISION, ...)` | `{node_name, tool_name, input}` | `{"node_name": "decide", "tool_name": "search"}` |

### 3.3 记忆类

| ActionType | 记录方法 | 数据格式 | 示例 |
|-----------|---------|---------|------|
| `MEMORY_WRITE` | `record_memory_write()` | `{key, value, source, memory_type}` | `{"key": "key_facts", "value": ["用户偏好 Python"]}` |
| `MEMORY_READ` | `record_memory_read()` | `{key, value, context, hit}` | `{"key": "user_pref", "hit": true}` |

### 3.4 状态类

| ActionType | 记录方法 | 数据格式 | 示例 |
|-----------|---------|---------|------|
| `STATE_CHANGE` | `record_state_change()` | `{node_name, trigger, diff}` | `{"diff": {"messages": {"type": "list", "old_len": 5, "new_len": 6}}}` |
| `NODE_EXECUTE` | `record_node_execute()` | `{node_name, input, output}` | `{"node_name": "search", "input": {"query": "..."}}` |

### 3.5 推理类

| ActionType | 记录方法 | 数据格式 | 示例 |
|-----------|---------|---------|------|
| `THINK` | `record_think()` | `{thought}` | `{"thought": "分析 JWT 过期问题"}` |

### 3.6 异常类

| ActionType | 记录方法 | 数据格式 | 示例 |
|-----------|---------|---------|------|
| `FAILURE` | `record_failure()` | `{error_type, error_message, context, recoverable, node_name, stack_trace}` | `{"error_type": "TimeoutError", "recoverable": true}` |

### 3.7 检索类

| ActionType | 记录方法 | 数据格式 | 示例 |
|-----------|---------|---------|------|
| `RETRIEVAL` | `record_retrieval()` | `{query, source, result_count, duration_ms, retrieved_docs}` | `{"query": "JWT 认证", "retrieved_docs": [{"title": "...", "snippet": "..."}]}` |
| `EVIDENCE` | `record_evidence()` | `{evidence_type, context, sources, final_prompt_messages}` | `{"sources": {"retrieved_docs_count": 3, "tool_results_count": 1}}` |

---

## 四、核心代码逐行解析

### 4.1 SDK Collector — 数据采集核心

**文件**：`sdk/collector.py`

#### 单例创建

```python
# line 258-323
class TrajectoryCollector:
    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls):
        # 双重检查锁定 — 线程安全的单例
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        with self._instance_lock:
            if self._initialized:
                return
            self._initialized = True
            self._buffer_lock = threading.Lock()   # 保护 steps 缓冲区
            self._flush_lock = threading.Lock()    # 防止并发 flush
            self._enabled = _env_bool("EVAL_ENABLED", True)
            self._api_base = _env_str("EVAL_API_BASE_URL", "http://127.0.0.1:8000")
            self._batch_size = _env_int("EVAL_BATCH_SIZE", 10)
```

**为什么用单例？**
- 所有请求共享同一个 HTTP 客户端（连接复用）
- 全局统一的配置管理
- 通过 ContextVar 实现会话隔离

#### 会话隔离（ContextVar）

```python
# line 232-240
@dataclass
class _CollectorSession:
    task_id: Optional[str] = None          # 当前任务 ID
    step_counter: int = 0                   # 步骤计数器
    steps: List[Dict[str, Any]] = field(default_factory=list)  # 缓冲区
    seen_events: _BoundedSet = ...          # 去重集合

# line 247 — 每个 async 任务有独立的 session
_collector_session: ContextVar[Optional[_CollectorSession]] = ContextVar(...)
```

**为什么用 ContextVar？**
- 并发的 Wiki 对话会同时调用 collector
- 每个对话需要独立的 task_id 和 steps 缓冲区
- ContextVar 在 asyncio 中自动隔离，无需手动传递

#### 异步方法（不阻塞事件循环）

```python
async def start_async(self, goal, context):
    """在线程池中执行 HTTP 请求，不阻塞事件循环。"""
    return await asyncio.to_thread(self.start, goal, context)

async def finish_async(self, *, auto_run=False):
    """在线程池中执行 HTTP 请求，不阻塞事件循环。"""
    return await asyncio.to_thread(self.finish, auto_run=auto_run)
```

**为什么用 `asyncio.to_thread`？**
- Wiki Agent 运行在同一 FastAPI 进程中
- 如果直接在事件循环中发 HTTP 请求，会阻塞其他请求处理
- `to_thread` 将 HTTP 请求放到独立线程，事件循环继续运行

---

### 4.2 Hooks 层 — Wiki Agent 与 SDK 的桥梁

**文件**：`app/wiki_agent/hooks.py`

```python
# line 15-27 — SDK 导入 + 降级
try:
    from sdk.collector import ActionType, get_collector
    _HAS_SDK = True
except ImportError:
    _HAS_SDK = False
    def _get_collector(): return None  # SDK 不可用时返回 None

# line 73-83 — 会话开始
async def emit_session_start(goal, session_id, context):
    collector = _get_collector()
    if collector is None or not collector.enabled:
        return                              # SDK 不可用 → 静默跳过
    try:
        await collector.start_async(goal, context)  # 创建评估任务
    except Exception as e:
        logger.warning("emit_session_start error: %s", e)  # 失败不阻塞

# line 85-93 — 检索记录
async def emit_retrieval(query, results, duration_ms):
    collector = _get_collector()
    if collector is None or not collector.enabled:
        return
    try:
        collector.record_retrieval(query, results, duration_ms=duration_ms)
    except Exception as e:
        logger.warning("emit_retrieval error: %s", e)

# line 121-131 — 会话结束
async def emit_session_end(session_id):
    collector = _get_collector()
    if collector is None or not collector.enabled:
        return
    try:
        await collector.finish_async(auto_run=True)  # flush + 触发评估
    except Exception as e:
        logger.warning("emit_session_end error: %s", e)
```

**为什么 hooks.py 要存在？**
1. **解耦**：graph.py 不直接依赖 SDK，只依赖 hooks.py
2. **降级**：SDK 不可用时所有操作静默跳过
3. **统一错误处理**：所有异常被捕获并记录日志，不阻塞业务

---

### 4.3 Graph.py — 业务代码中的调用点

**文件**：`app/wiki_agent/agent/graph.py`

```python
# line 30 — 导入 hooks
from app.wiki_agent.hooks import (
    emit_key_facts, emit_retrieval, emit_response,
    emit_session_end, emit_session_start
)

# line 595-654 — run_chat_stream()
async def run_chat_stream(user_message, chat_history, session_id=None):
    # ... 初始化 ...

    # ★ 调用点 1：会话开始
    await emit_session_start(user_message, session_id or "",
        {"thread_id": thread_id, "mode": "stream"})

    # ... 执行 LangGraph ...

    # ★ 调用点 2：在 search 节点内
    # line 364: 检索完成后
    await emit_retrieval(user_message, ctx.wiki_results, duration_ms)

    # line 399: 事实提取后
    await emit_key_facts([f.get("content", "") for f in facts])

    # ★ 调用点 3：在 respond 节点内
    # line 454: 回复生成后
    await emit_response(session_id, collected)

    # ★ 调用点 4：会话结束（finally 块）
    finally:
        await emit_session_end(session_id or "")  # 确保总能执行
```

**为什么调用点在这些位置？**

| 调用点 | 位置 | 原因 |
|--------|------|------|
| `emit_session_start` | 对话开始时 | 创建评估任务，开始缓冲 |
| `emit_retrieval` | 检索完成后 | 记录检索查询和结果，供 RetrievalEvaluator 消费 |
| `emit_key_facts` | 事实提取后 | 记录记忆写入，供 MemoryEvaluator 消费 |
| `emit_response` | 回复生成后 | 记录最终回复，供 RetrievalEvaluator 做幻觉检测 |
| `emit_session_end` | finally 块 | 确保 flush 轨迹，即使客户端断开也能触发评估 |

---

---

## 五、数据消费：6 个评估器

### 5.1 评估器如何提取数据

**文件**：`app/evaluators/base.py`

每个评估器通过 `_extract_*()` 方法从轨迹中提取相关的步骤：

```python
# line 187 — 提取计划步骤
def _extract_plans(self, trajectory):
    return [s for s in trajectory if s.get("action_type") == "plan"]

# line 207 — 提取工具调用
def _extract_tool_calls(self, trajectory):
    return [s for s in trajectory if s.get("action_type") == "tool_call"]

# line 261 — 提取记忆事件
def _extract_memory_events(self, trajectory):
    return [s for s in trajectory
            if s.get("action_type") in ("memory_write", "memory_read")]

# line 306 — 提取检索事件
def _extract_retrievals(self, trajectory):
    return [s for s in trajectory if s.get("action_type") == "retrieval"]
```

### 5.2 评估器消费的 ActionType 映射

```
轨迹数据 (14 种 ActionType)
    │
    ├─ PLAN, PLAN_UPDATE ──────→ PlanningEvaluator
    │    └─ 评估：覆盖度、排序、粒度、完整性
    │
    ├─ 所有非 PLAN 步骤 ───────→ TacticalEvaluator
    │    └─ 评估：相关性、效率、正确性
    │
    ├─ TOOL_CALL, TOOL_RESULT ─→ ToolUseEvaluator
    │    └─ 评估：选择质量、参数准确、结果利用
    │
    ├─ MEMORY_WRITE, MEMORY_READ → MemoryEvaluator
    │    └─ 评估：保持度、相关性、一致性
    │
    ├─ REPLAN, FAILURE ────────→ ReplanEvaluator
    │    └─ 评估：触发时机、适应质量、学习能力
    │
    └─ RETRIEVAL, EVIDENCE ────→ RetrievalEvaluator
         └─ 评估：相关性、证据准确、覆盖度、幻觉检测
```

### 5.3 两个 Agent 的 ActionType 完整覆盖

两个 Agent 都覆盖全部 14 种 ActionType，缺失的类型是因为 Agent 本身没有对应行为：

| ActionType | Wiki Agent | Agent 行为对应 |
|-----------|:---:|-------------|
| `PLAN` | ✅ | 生成计划 |
| `PLAN_UPDATE` | ✅ | 更新计划/进度 |
| `TOOL_CALL` | ✅ | 调用工具 |
| `TOOL_RESULT` | ✅ | 工具返回 |
| `TOOL_DECISION` | ✅ | 决定调用哪个工具 |
| `MEMORY_WRITE` | ✅ | 写入记忆 |
| `MEMORY_READ` | ✅ | 读取记忆 |
| `STATE_CHANGE` | ✅ | 状态变化 |
| `NODE_EXECUTE` | ✅ | 节点执行 |
| `THINK` | ✅ | 思考推理 |
| `FAILURE` | ✅ | 异常/失败 |
| `REPLAN` | ✅ | 失败后重规划（create↔update 替代） |
| `RETRIEVAL` | ✅ | RAG 检索 |
| `EVIDENCE` | ✅ | 构建证据池 |

**覆盖率：14/14（100%）**

### 5.4 评估流程

```python
# app/services/evaluation_service.py:339-461
async def run_evaluation(self, task_id, ...):
    # 1. 从 DB 加载轨迹
    trajectory = await self._get_trajectory(task_id)

    # 2. 6 个评估器并行执行
    results = await evaluate_parallel(goal, trajectory, context)

    # 3. 保存结果
    await self._persist_evaluation_results(evaluation_id, results)
```

---

## 六、数据库表结构

### 6.1 核心表

```sql
-- 评估任务
CREATE TABLE agent_tasks (
    id TEXT PRIMARY KEY,
    goal TEXT NOT NULL,                    -- 任务目标
    context JSON,                          -- 任务上下文
    status TEXT DEFAULT 'pending',         -- pending/running/completed/failed
    workspace_id TEXT,
    created_at TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

-- 轨迹步骤
CREATE TABLE agent_trajectories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES agent_tasks(id),
    step_number INTEGER NOT NULL,          -- 步骤序号
    action_type TEXT NOT NULL,             -- 14 种 ActionType 之一
    action_detail JSON NOT NULL,           -- 动作详情（结构化数据）
    observation TEXT,                      -- 观察结果（文本）
    timestamp TIMESTAMP NOT NULL           -- UTC 时间戳
);

-- 评估结果
CREATE TABLE evaluations (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES agent_tasks(id),
    status TEXT DEFAULT 'pending',         -- pending/in_progress/completed/failed

    -- 6 维评分
    planning_score FLOAT,
    tactical_score FLOAT,
    tool_use_score FLOAT,
    memory_score FLOAT,
    replan_score FLOAT,
    retrieval_score FLOAT,
    overall_score FLOAT,                   -- 加权综合分

    -- 6 维反馈（含 Judge 原始数据）
    planning_feedback JSON,
    tactical_feedback JSON,
    tool_use_feedback JSON,
    memory_feedback JSON,
    replan_feedback JSON,
    retrieval_feedback JSON,

    -- 元数据
    prompt_version TEXT,
    model_name TEXT,
    model_provider TEXT,
    workspace_id TEXT,
    created_at TIMESTAMP,
    completed_at TIMESTAMP
);
```

### 6.2 action_detail JSON 结构示例

```json
// PLAN 类型
{
    "goal": "实现用户登录功能",
    "context": {"key_facts": ["项目使用 JWT", "数据库是 PostgreSQL"]}
}

// TOOL_CALL 类型
{
    "tool_name": "python_execute",
    "input": {"code": "import jwt; print(jwt.__version__)"},
    "duration_ms": 1234.5
}

// RETRIEVAL 类型
{
    "query": "JWT 认证最佳实践",
    "source": "hybrid_search",
    "result_count": 5,
    "duration_ms": 156.7,
    "retrieved_docs": [
        {"title": "JWT 认证指南", "path": "auth/jwt-guide.md", "snippet": "...", "score": 0.92}
    ]
}

// MEMORY_WRITE 类型
{
    "key": "key_facts",
    "value": ["用户偏好 Python", "项目使用 asyncio"],
    "source": "llm_extraction",
    "memory_type": "fact"
}
```

---

## 七、为什么能获取到数据

### 7.1 根本原因：显式埋点 + 框架注入

评估平台能获取数据的**根本原因**是 Agent 代码中**显式调用**了 `record_*()` 方法。

这不是"零侵入"的自动采集，而是**有意识的数据暴露**：

| 采集方式 | 机制 | 侵入性 |
|---------|------|--------|
| SDK 采集 | Agent 代码显式调用 `collector.record_*()` | 中（需改业务代码） |
| Wiki Agent hooks | graph.py 显式调用 `emit_*()` | 中（6 个调用点） |

### 7.2 SDK 采集的工作原理

```
Agent 代码
    │
    ├─ "我要记录这个操作" → 调用 collector.record_retrieval(...)
    │                              │
    │                              ▼
    │                    构建 step dict
    │                    {step_number, action_type, action_detail, observation, timestamp}
    │                              │
    │                              ▼
    │                    追加到内存缓冲区 (session.steps)
    │                              │
    │                    缓冲区满或 finish() 时
    │                              ▼
    │                    批量 POST 到评估平台 API
    │                              │
    │                              ▼
    │                    EvaluationService.add_trajectory()
    │                    写入 agent_trajectories 表
    │                              │
    │                              ▼
    │                    run_evaluation()
    │                    6 个评估器读取轨迹，LLM 评分
    │                              │
    │                              ▼
    │                    写入 evaluations 表
    │                    前端展示 6 维雷达图
```

### 7.3 关键设计决策

| 决策 | 原因 |
|------|------|
| 用内存缓冲而非实时上传 | 减少 HTTP 请求次数，提升性能 |
| 用 ContextVar 而非全局变量 | 支持并发请求的会话隔离 |
| 用 asyncio.to_thread 发 HTTP | 不阻塞事件循环，避免自死锁 |
| 用去重集合而非简单追加 | 防止重试导致的重复记录 |
| 用 LLM-as-Judge 而非规则 | 评估需要理解语义，规则无法覆盖 |

### 7.4 数据完整性保障

| 保障机制 | 说明 |
|---------|------|
| 失败回退缓冲 | flush 失败时步骤回退到本地缓冲，下次 flush 重试 |
| 指数退避重试 | HTTP 请求最多重试 3 次（0.5s → 1s → 2s） |
| finally 块保证 | `emit_session_end` 在 finally 块中，确保总能执行 |
| 去重集合 | `_BoundedSet`（LRU，5000 条）防止重复记录 |
| 离线模式 | `EVAL_ENABLED=false` 时静默跳过，不阻塞 Agent |

---

# 技术选型报告 — Agent Runtime Evaluation Platform

> 版本：v0.1.0 | 更新日期：2026-06-30

---

## 目录

1. [项目概述](#1-项目概述)
2. [后端核心](#2-后端核心)
3. [AI/LLM 框架](#3-aillm-框架)
4. [RAG 检索系统](#4-rag-检索系统)
5. [前端技术栈](#5-前端技术栈)
6. [数据存储](#6-数据存储)
7. [基础设施与可观测性](#7-基础设施与可观测性)
8. [开发工具链](#8-开发工具链)
9. [选型决策矩阵总览](#9-选型决策矩阵总览)

---

## 1. 项目概述

本平台是一个 **AI Agent 全维度评估系统**，支持两种评测模式：

- **Sandbox 评测**：在隔离 Docker 容器中执行 Agent 代码，实时采集轨迹
- **外部轨迹评测**：通过 Python SDK 采集已有 Agent 的运行轨迹，离线评估

覆盖 **规划、决策、工具使用、记忆、重规划、检索** 6 大能力维度，内置 Wiki Agent 作为 RAG 知识库管理演示。

技术选型的核心原则：

| 原则 | 说明 |
|------|------|
| **生产就绪** | 选择有大规模生产验证的技术，而非实验性框架 |
| **异步优先** | 全链路 async/await，适配 LLM 长耗时调用场景 |
| **可扩展** | 模块化设计，各组件可独立替换 |
| **国产模型兼容** | 优先支持国内 LLM 服务商（DeepSeek、GLM、Qwen） |

---

## 2. 后端核心

### 2.1 Python 3.11+

| 候选 | 选择 | 理由 |
|------|------|------|
| Python 3.10 | ❌ | 缺少 `ExceptionGroup` 等新特性 |
| **Python 3.11+** | ✅ | 性能提升 10-60%，`TaskGroup` 原生异步编排，`tomllib` 内置 |
| Python 3.12+ | ❌ | 部分依赖尚未完全兼容 |

**关键收益**：`asyncio.TaskGroup` 简化了多评测器并行执行的错误处理。

### 2.2 FastAPI

| 候选 | 选择 | 理由 |
|------|------|------|
| Flask | ❌ | 同步阻塞模型，LLM 长耗时调用会阻塞 worker |
| Django | ❌ | 过重，ORM/Admin 等功能用不上 |
| **FastAPI** | ✅ | 原生 async、自动 OpenAPI 文档、Pydantic 集成、SSE 支持 |
| Tornado | ❌ | 缺少类型校验和自动文档生成 |

**关键收益**：
- `SSE-Starlette` 直接集成，实时推送评测进度到前端
- Pydantic v2 自动校验请求/响应，减少 60% 的手写校验代码
- 依赖注入系统天然适配多 LLM Provider 切换

### 2.3 Celery + Redis

| 候选 | 选择 | 理由 |
|------|------|------|
| **Celery + Redis** | ✅ | 成熟的分布式任务队列，Redis 作为 broker 和 result backend |
| asyncio 原生 | ❌ | 单进程，无法水平扩展；进程崩溃会丢失任务 |
| RQ (Redis Queue) | ❌ | 功能过于简单，缺少任务优先级、重试策略、监控面板 |
| Dramatiq | ❌ | 社区规模小，文档不完善 |

**关键收益**：
- 评测任务可跨 Worker 分发，支持并发评测
- 任务重试和超时机制，LLM 调用失败自动恢复
- Flower 监控面板实时观察任务状态

### 2.4 Pydantic v2

| 候选 | 选择 | 理由 |
|------|------|------|
| **Pydantic v2** | ✅ | Rust 核心加速（pydantic-core），性能提升 5-50 倍 |
| Pydantic v1 | ❌ | 性能瓶颈，v2 已成为社区标准 |
| dataclasses | ❌ | 缺少运行时校验和序列化能力 |
| attrs | ❌ | 缺少 JSON Schema 自动生成 |

**关键收益**：
- 与 FastAPI 深度集成，自动生成 OpenAPI Schema
- `pydantic-settings` 直接从 `.env` 加载配置，类型安全
- 评测结果的序列化/反序列化零成本

---

## 3. AI/LLM 框架

### 3.1 为什么选择 LangGraph（核心问题）

这是本项目最关键的架构决策。以下是详细对比：

#### 候选方案对比

| 维度 | LangGraph | LangChain Agent | AutoGen | CrewAI | 自研状态机 |
|------|-----------|-----------------|---------|--------|-----------|
| **状态管理** | 显式 TypedDict，可检查可持久化 | 隐式，黑盒 | 对话级状态 | 任务级状态 | 完全自控 |
| **流程控制** | 条件边、循环、中断恢复 | 链式，难中断 | 对话驱动 | 角色驱动 | 完全自控 |
| **Human-in-the-Loop** | 原生 `interrupt()` + checkpoint | 需 hack | 原生支持 | 不支持 | 需自实现 |
| **可视化调试** | LangGraph Studio | 无 | 有限 | 无 | 需自建 |
| **持久化** | Checkpoint（SQLite/Postgres） | 无原生支持 | 无 | 无 | 需自实现 |
| **并行执行** | 原生 `Send()` API | 不支持 | 支持 | 支持 | 需自实现 |
| **流式输出** | 节点级流式 | 链级流式 | 不支持 | 不支持 | 需自实现 |
| **社区生态** | LangChain 生态 | 最大 | Microsoft 背书 | 快速增长 | 无 |

#### 选择 LangGraph 的 5 个核心理由

**① 显式状态图，可审计可调试**

```python
# 评测流程的 LangGraph 表达 — 每个节点的状态转换都是显式的
graph = StateGraph(EvaluationState)
graph.add_node("collect", collect_trajectory)
graph.add_node("evaluate", run_evaluators)      # 6 个评测器并行
graph.add_node("aggregate", aggregate_scores)
graph.add_conditional_edges("evaluate", route_to_aggregate)
```

对比 LangChain Agent 的 `agent_executor.invoke()` — 内部状态完全不可见，出错时无法定位是哪个环节失败。

**② Human-in-the-Loop 原生支持**

Wiki Agent 的知识库 CRUD 需要用户确认：

```python
async def execute(state: WikiState, config: RunnableConfig) -> WikiState:
    user_confirmed = interrupt({})  # 暂停，等待用户确认
    if not user_confirmed:
        return {...}  # 用户取消
    # 执行操作...
```

LangGraph 的 `interrupt()` + checkpoint 机制让状态暂停/恢复成为一等公民。AutoGen 虽然也支持，但它是对话驱动的，不适合我们的确定性流程。

**③ 评测器并行执行**

6 个评测器需要并行运行，LangGraph 的 `Send()` API 天然支持：

```python
# evaluation_graph.py
graph.add_conditional_edges(
    "dispatch",
    lambda state: [Send(eval_name, state) for eval_name in EVALUATORS],
)
```

LangChain Agent 不支持并行分支，AutoGen 的并行是对话级别的，粒度太粗。

**④ 状态持久化与断点续传**

```python
# 评测任务中断后可从 checkpoint 恢复
checkpointer = AsyncSqliteSaver(conn=conn)
graph = create_evaluation_graph(checkpointer)
result = await graph.ainvoke(initial_state, config)
```

长耗时的评测任务（可能涉及数十次 LLM 调用）需要断点续传能力。LangGraph 的 checkpoint 机制让这成为开箱即用的功能。

**⑤ 与 LangChain 生态无缝集成**

项目使用 LangChain 封装 LLM 调用（`ChatOpenAI`、`ChatAnthropic`），LangGraph 与 LangChain 共享 `BaseMessage`、`RunnableConfig` 等核心类型，零适配成本。

#### 为什么不选其他方案

| 方案 | 淘汰原因 |
|------|---------|
| **LangChain Agent** | 黑盒执行，无法插入评测采集点；不支持并行分支；无状态持久化 |
| **AutoGen** | 对话驱动模型不适合确定性评测流程；Python SDK 质量不稳定（v0.2→v0.4 大量 breaking changes） |
| **CrewAI** | 角色驱动模型更适合创意协作，不适合结构化评测；缺少 Human-in-the-Loop |
| **自研状态机** | 开发成本高（需自实现持久化、并行、中断恢复）；缺少调试工具 |

### 3.2 LangChain

| 候选 | 选择 | 理由 |
|------|------|------|
| **LangChain** | ✅ | LLM 调用抽象层，统一 DeepSeek/OpenAI/Anthropic/ZhipuAI/Qwen 接口 |
| LiteLLM | ❌ | 纯代理模式，缺少 Chain/Tool 抽象 |
| 直接调用各厂商 SDK | ❌ | 每换一个模型改一遍代码，维护成本高 |

**关键收益**：
- `ChatOpenAI` 一个类覆盖所有 OpenAI 兼容 API（DeepSeek、GLM、Qwen）
- `BaseMessage` 统一消息格式，评测器无需关心底层模型
- 与 LangGraph 共享类型系统

### 3.3 多 LLM Provider

本平台支持 5 个 LLM 服务商，原因：

| Provider | 定位 | 选择理由 |
|----------|------|---------|
| **DeepSeek** | 默认 Provider | 性价比最高，中文能力强，OpenAI 兼容 API |
| **ZhipuAI (GLM)** | 备选/共识 | 国产头部，`glm-4-flash` 免费额度，适合高频调用 |
| **Qwen (DashScope)** | 共识机制 | 阿里云生态，与业务系统集成方便 |
| **OpenAI** | 高质量评测 | GPT-4o 推理能力强，适合高要求评测场景 |
| **Anthropic** | 高质量评测 | Claude 长上下文优势，适合复杂 Agent 轨迹分析 |

**多模型共识机制**：评测打分时，跨 3 个 Provider（DeepSeek + GLM + Qwen）独立评分，取均值和置信度，消除单模型偏见。

---

## 4. RAG 检索系统

### 4.1 向量数据库：Milvus Lite

| 候选 | 选择 | 理由 |
|------|------|------|
| **Milvus Lite** | ✅ | 本地文件模式，零部署；生产可无缝升级 Milvus Server |
| Chroma | ❌ | 嵌入式模式性能差，大数据量不稳定 |
| FAISS | ❌ | 纯库，缺少元数据过滤、持久化管理 |
| Pinecone | ❌ | 纯云服务，国内访问不稳定，有数据合规风险 |
| Weaviate | ❌ | 部署复杂，Wiki Agent 场景过重 |

**关键收益**：
- `pymilvus.MilvusClient` 单文件模式，开发零配置
- COSINE 距离 + 512 维向量，中文语义检索精度高
- 生产环境可切换到 Milvus Server（只需改 URI）

### 4.2 Embedding 模型：BAAI/bge-small-zh-v1.5

| 候选 | 选择 | 理由 |
|------|------|------|
| **bge-small-zh-v1.5** | ✅ | 中文 MTEB 排行前列，512 维平衡性能与精度 |
| bge-large-zh-v1.5 | ❌ | 1024 维，内存占用翻倍，推理速度慢 2-3 倍 |
| text2vec-large-chinese | ❌ | 社区维护减少，更新滞后 |
| OpenAI text-embedding-3-small | ❌ | API 调用成本，国内访问不稳定 |
| M3E | ❌ | 中文 MTEB 评测分数低于 bge 系列 |

**关键收益**：
- 本地推理，零 API 成本
- 512 维向量，Milvus 存储和检索效率最优
- `sentence-transformers` 框架，一行代码切换其他模型

### 4.3 Reranker：BAAI/bge-reranker-base

| 候选 | 选择 | 理由 |
|------|------|------|
| **bge-reranker-base** | ✅ | Cross-Encoder 精度高于 Bi-Encoder，中文优化 |
| bge-reranker-large | ❌ | 推理速度慢 3 倍，精度提升有限 |
| Cohere Rerank | ❌ | API 调用成本，国内访问不稳定 |
| 不用 Reranker | ❌ | RRF 融合后精度下降明显，尤其混合检索场景 |

**关键收益**：
- Cross-Encoder 对 query-document pair 做精细相关性判断
- 与 bge embedding 同系列，语义空间一致
- 可通过 `RERANK_ENABLED=false` 一键关闭

### 4.4 混合检索策略

```
Query → 语义搜索(Milvus) + BM25(jieba) → RRF 融合 → Cross-Encoder 重排 → Top-K
```

| 策略 | 选择 | 理由 |
|------|------|------|
| 纯语义搜索 | ❌ | 对精确关键词（如函数名、API 名）召回率低 |
| 纯 BM25 | ❌ | 无法理解语义相似（如"向量数据库"≈"vector database"） |
| **RRF 混合 + Rerank** | ✅ | 互补优势，RRF 倒数秩融合消除分数尺度差异 |

### 4.5 Query 改写 Pipeline

```
用户 Query → 上下文补齐(代词消解) → 路由分类(LLM) → 策略改写 → 相似度校验 → 检索
```

| 方案 | 选择 | 理由 |
|------|------|------|
| 不改写直接检索 | ❌ | 多轮对话指代消解缺失，口语化 query 召回率低 |
| **路由分类 + 多策略改写** | ✅ | 按 query 类型选择最优策略，成本可控 |
| 全量 Multi-Query | ❌ | 每次 3-5 个 LLM 调用，成本和延迟不可接受 |

---

## 5. 前端技术栈

### 5.1 Vue 3 + TypeScript

| 候选 | 选择 | 理由 |
|------|------|------|
| React | ❌ | 缺少官方状态管理和路由方案，选型决策多 |
| **Vue 3** | ✅ | Composition API + 官方全家桶（Pinia + Vue Router），开箱即用 |
| Angular | ❌ | 学习曲线陡峭，中小型项目过重 |
| Svelte | ❌ | 生态不成熟，组件库选择少 |

**关键收益**：
- `Composition API` + `<script setup>` 代码简洁，类型推导好
- Vue 3 响应式系统对复杂评测状态（6 个维度实时更新）支持优秀
- 中文社区活跃，Element Plus 文档完善

### 5.2 Element Plus

| 候选 | 选择 | 理由 |
|------|------|------|
| **Element Plus** | ✅ | Vue 3 生态最成熟的 UI 库，中文文档完善 |
| Ant Design Vue | ❌ | Vue 版本更新滞后于 React 版本 |
| Vuetify | ❌ | Material Design 风格，与项目需求不匹配 |
| Naive UI | ❌ | 组件丰富度不如 Element Plus |

### 5.3 ECharts

| 候选 | 选择 | 理由 |
|------|------|------|
| **ECharts** | ✅ | 国产图表库，中文文档完善，图表类型丰富 |
| Chart.js | ❌ | 图表类型有限，缺少雷达图、热力图等高级图表 |
| D3.js | ❌ | 过于底层，开发成本高 |
| Highcharts | ❌ | 商业许可，成本问题 |

**关键收益**：
- 雷达图展示 6 维评估结果
- 热力图展示评估对比矩阵
- `vue-echarts` 封装，响应式绑定

### 5.4 Vite

| 候选 | 选择 | 理由 |
|------|------|------|
| **Vite** | ✅ | 原生 ESM，HMR 毫秒级，Vue 3 官方推荐 |
| Webpack | ❌ | 配置复杂，HMR 慢 |
| Turbopack | ❌ | 尚未稳定 |

---

## 6. 数据存储

### 6.1 关系型数据库

| 环境 | 选择 | 理由 |
|------|------|------|
| 开发 | **SQLite (aiosqlite)** | 零配置，文件级数据库，开发迭代快 |
| 生产 | **PostgreSQL (asyncpg)** | 事务安全、JSON 支持、全文搜索、水平扩展 |

**SQLAlchemy 2.0** 作为 ORM，统一两个数据库的访问接口，切换只需改连接字符串。

### 6.2 缓存层：Redis

| 候选 | 选择 | 理由 |
|------|------|------|
| **Redis** | ✅ | 缓存 + 消息队列 + 速率限制，一石三鸟 |
| Memcached | ❌ | 仅支持缓存，缺少消息队列能力 |
| 本地内存缓存 | ❌ | 多 Worker 间无法共享 |

**用途**：
- LLM 响应缓存（相同 prompt 不重复调用）
- 评测报告缓存
- Celery broker/result backend
- API 速率限制（滑动窗口算法）

### 6.3 向量存储

见 [4.1 Milvus Lite](#41-向量数据库milvus-lite)。

---

## 7. 基础设施与可观测性

### 7.1 容器化

| 组件 | 选择 | 理由 |
|------|------|------|
| **Docker** | ✅ | 主应用容器化 + Sandbox 隔离执行 |
| **Docker Compose** | ✅ | 一键启动 Redis + Backend + Frontend |
| Kubernetes | ❌ | 当前规模不需要，未来可平滑升级 |

**Sandbox 隔离设计**：
- Agent 代码在独立容器中执行，限制 CPU/内存/网络
- 预装常用 Python/Node.js 库，减少冷启动时间
- 执行超时自动销毁，防止资源泄漏

### 7.2 可观测性

| 维度 | 技术 | 选择理由 |
|------|------|---------|
| **链路追踪** | OpenTelemetry + Jaeger | CNCF 标准，LLM 调用链路可视化 |
| **指标采集** | Prometheus | 行业标准，`/metrics` 端点开箱即用 |
| **结构化日志** | structlog | JSON 格式生产日志，correlation ID 关联追踪 |

**为什么选 OpenTelemetry 而非 Datadog/New Relic**：
- 开源免费，无 Vendor Lock-in
- 支持自托管 Jaeger，数据不出境
- SDK 覆盖 Python/JavaScript/Go，未来扩展无限制

### 7.3 速率限制

API 速率限制使用 **Redis 滑动窗口算法**，而非固定窗口：

| 算法 | 选择 | 理由 |
|------|------|------|
| 固定窗口 | ❌ | 窗口边界处突发流量，限流不精确 |
| **滑动窗口** | ✅ | 平滑限流，精确控制 QPS |
| 令牌桶 | ❌ | 实现复杂，Redis 原生支持滑动窗口更简单 |

---

## 8. 开发工具链

### 8.1 代码质量

| 工具 | 选择 | 替代 | 理由 |
|------|------|------|------|
| **Ruff** | ✅ | flake8 + isort + black | 单工具替代 3 个，Rust 实现速度快 100 倍 |
| **mypy** | ✅ | pyright | Python 社区标准，类型检查严格模式 |
| **pytest** | ✅ | unittest | fixtures 生态强大，插件丰富 |

### 8.2 测试策略

| 层级 | 工具 | 覆盖范围 |
|------|------|---------|
| 单元测试 | pytest + mock | 各模块独立测试 |
| 集成测试 | pytest + httpx | API 端点测试 |
| 回归测试 | Golden Test Suite | 评测器输出稳定性 |
| CI Gate | `run_ci_gate.py` | PR 合并前自动验证 |

### 8.3 构建与部署

| 工具 | 选择 | 理由 |
|------|------|------|
| **Hatchling** | ✅ | PEP 517 构建后端，pyproject.toml 原生支持 |
| **Makefile** | ✅ | 统一开发命令入口（`make test`, `make lint`） |
| **Alembic** | ✅ | SQLAlchemy 官配迁移工具 |

---

## 9. 选型决策矩阵总览

### 核心技术栈

| 领域 | 选择 | 核心理由 |
|------|------|---------|
| 语言 | Python 3.11+ | AI 生态标准，异步支持完善 |
| Web 框架 | FastAPI | 原生 async，自动文档，SSE 支持 |
| Agent 编排 | **LangGraph** | 显式状态图、Human-in-the-Loop、并行执行、断点续传 |
| LLM 抽象 | LangChain | 统一 5 个 Provider 接口 |
| 向量数据库 | Milvus Lite | 零部署，生产可升级 |
| 混合检索 | RRF + Rerank | 语义 + 关键词互补，精度最优 |
| 前端框架 | Vue 3 + Element Plus | 官方全家桶，中文生态完善 |
| 数据库 | SQLite/PostgreSQL | 开发零配置，生产可扩展 |
| 缓存 | Redis | 缓存 + 队列 + 限流三合一 |
| 可观测性 | OpenTelemetry | CNCF 标准，无 Vendor Lock-in |

### 不选择的备选方案及原因

| 淘汰方案 | 淘汰原因 |
|---------|---------|
| LangChain Agent | 黑盒执行，无法插入评测采集点 |
| AutoGen | 对话驱动不适合确定性流程，SDK 不稳定 |
| CrewAI | 角色模型不适合结构化评测 |
| Chroma | 大数据量性能不稳定 |
| React | 缺少官方全家桶，选型成本高 |
| Webpack | 配置复杂，HMR 慢 |
| Django | 过重，ORM/Admin 用不上 |

---

> 本报告基于项目 v0.1.0 版本技术栈编写，随着项目演进可能需要更新。

---

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

---

# Agent Runtime Evaluation — 设计说明

> **入口**: [README.md](../README.md) · **架构**: [architecture.md](architecture.md) · **开发者指南**: [developer_guide.md](developer_guide.md)

## 1. 为什么做 Runtime Evaluation

传统 Prompt Evaluation 只评最终输出，无法发现 Agent 在运行过程中的决策问题。本平台评估 **每一步行为质量**：

- 计划是否合理（Planning）
- 下一步动作是否恰当（Tactical）
- 工具是否选对、参数是否正确（Tool Use）
- 上下文是否保持（Memory）
- 失败后是否有效重规划（Replan）
- RAG 检索是否可靠、有无幻觉（Retrieval）

## 2. 六维评估体系

| 维度 | 权重 | 方法 |
|------|------|------|
| Planning | 20% | LLM-as-Judge |
| Tactical | 20% | LLM-as-Judge |
| Tool Use | 15% | LLM-as-Judge |
| Memory | 15% | LLM-as-Judge |
| Replan | 15% | LLM-as-Judge |
| Retrieval | 15% | LLM-as-Judge + 幻觉检测 |

默认通过 `evaluate_parallel()` 六路并发，耗时约 15–30 秒。

## 3. 架构

```
Trajectory (SDK/Wiki Agent) → EvaluationService → 6 Evaluators (并行)
                                         ↓
                                   Redis Cache (可选)
                                   • LLM 结果缓存 24h
                                   • 报表聚合 5min
                                   • Task 查询 60s
                                   • Dashboard 30s
                                   • 接口限流 Sorted Set
                                         ↓
                                    DB → Reports API → Vue Dashboard
```

## 4. Redis 缓存策略

**设计原则**: Redis 为可选依赖，不可用时应用正常运行（所有 cache 操作 try/except 后静默返回 None/False）。

| 场景 | 策略 | 理由 |
|------|------|------|
| 报表聚合 | 全量查询结果缓存，写入时 pattern DEL | 聚合查询 O(N)，Dashboard 高频刷新 |
| LLM 评估结果 | prompt SHA-256 哈希做 key，24h TTL | 相同轨迹+目标 = 相同评估结果，节省 API 费用 |
| 接口限流 | Sorted Set 滑动窗口 | 防止 LLM API 费用失控，Redis 不可用时放行 |
| Task/Trajectory | 短 TTL + 写入时失效 | 减少评估流程内重复查询（get_task 单次流程调用 2-4 次） |
| Wiki 会话 | Write-through，SQLite 为 source of truth | 每条消息都查 SQLite，加缓存后读延迟 <1ms |

## 5. 与 RAGAS / LangSmith 的差异

- **RAGAS**：专注 RAG 检索与生成质量
- **LangSmith**：通用 tracing + 实验平台
- **本平台**：Agent **运行时** 全链路六维（Planning / Tactical / Tool Use / Memory / Replan / Retrieval），含轨迹动作级分析、迭代对比、多模型共识

## 6. Wiki Agent 闭环

Wiki Agent 聊天时通过 `EvaluationTrace` 采集 trajectory（含 retrieval 步骤），可选自动触发评估，形成「Agent 运行 → 评估 → 改进」演示闭环。

## 7. 效果展示

### 前端可视化体系

| 页面 | 图表类型 | 数据来源 | 刷新时机 |
|------|----------|----------|----------|
| 仪表板 | 雷达图 + 趋势折线 + 柱状图 + 统计卡片 | `GET /reports/summary` + `GET /reports/trends` | 页面加载，缓存 30s |
| 评估详情 | 6 维评分卡 + 雷达图 + 时间线 | `GET /evaluations/{id}` | 评估完成时自动刷新 |
| 数据分析 | 分布直方图 + 热力图 + 多折线叠加 | `GET /reports/dimensions/{dim}` + `GET /reports/trends` | 页面加载 |
| Replay 调试 | 步骤展开列表，LLM 原始 Prompt/Response | `GET /evaluations/{id}/replay` | 手动点击 |
| Judge 透明面板 | 原始 Judge Prompt + Response + 解析后分数 | `GET /evaluations/{id}/judge-raw/{dim}` | 手动点击 |
| 系统设置 | 状态标签 + 配置表单 | `GET /system/health` | 页面加载 + 手动刷新 |

### 评分展示规范

| 等级 | 范围 | 颜色 | UI 展示 |
|------|------|------|---------|
| 优秀 | ≥ 80 | `success` (绿色) | 标签 + 绿色进度条 |
| 良好 | ≥ 60 | `warning` (黄色) | 标签 + 黄色进度条 |
| 一般 | ≥ 40 | `orange` (橙色) | 标签 + 橙色进度条 |
| 较差 | < 40 | `danger` (红色) | 标签 + 红色进度条 |

### Consensus 多模型对比

多模型共识评估的输出在 Dashboard 上以横向表格 + 柱状图展示：

```
═══ 规划维度 Consensus ═══
deepseek-chat:     72%  ████████████████████████████░░  72
glm-4:             75%  ██████████████████████████████  75
qwen-plus:         70%  ██████████████████████████░░░░  70
────────────────────────────────────────────────────
综合均分: 72.3  |  分歧度 (std): 2.1  |  一致性: 高 ✅
```

## 8. 关键设计要点

| 要点 | 方案 | 理由 |
|------|------|------|
| **缓存隔离** | Cache key 包含模型名 | 避免多模型共识时缓存串用导致 std=0 |
| **优雅降级** | 所有外部依赖 try/except 兜底 | Redis/Celery/Docker 不可用时核心功能不掉 |
| **并行评估** | `asyncio.gather` 并发 6 评估器 | 单次评估 15-30s，串行需 90-180s |
| **Ghost Plan 过滤** | 跳过只有 {goal,context} 的 plan 步骤 | 避免任务创建时的空 plan 被误判为真实规划 |
| **增量重算** | Trajectory Diff → 只重算变化维度 | 修改 prompt 后节省 2/3 评估时间 |
| **版本追踪** | evaluation 记录 prompt_version / model_name | 每次评估可追溯使用的配置版本 |

---

# Agent Runtime Evaluation Platform — 技术深度剖析

> 面试用技术文档，聚焦业务场景、遇到的问题、解决方案和实现细节。

---

## 一、业务场景：为什么要做这个平台

### 1.1 现有方案的痛点

在 AI Agent 开发中，评估是一个被严重低估的环节。现有的评估方案存在三个根本性问题：

**RAGAS / LangSmith 的局限**：RAGAS 只评 RAG 检索质量，不覆盖 Agent 的规划、决策、工具使用等维度。LangSmith 是通用 tracing 平台，不做结构化的质量评估。两者都无法回答"Agent 的决策过程质量如何"这个问题。

**Prompt Evaluation 的错位**：很多团队用 Prompt Evaluation（如 BLEU、ROUGE）来评估 Agent，但这只评最终输出文本质量，不评估运行时行为。一个 Agent 可能最终输出了正确的答案，但中间过程极其低效（绕了 10 步才完成本该 3 步完成的任务），这种问题 Prompt Evaluation 完全发现不了。

**缺乏诊断能力**：即使发现 Agent 质量不行，现有的评估方案也无法告诉你"哪里不行"。你只知道"成功率 30%"，但不知道是规划有问题、工具用错了、还是记忆丢失了。

### 1.2 我们的定位

本平台的核心定位是 **Agent Runtime Evaluation**——评估 Agent 运行时每一步的决策质量，而不是最终输出质量。

类比：传统评估是"考试只看总分"，我们是"考试看每道题的解题过程"。

具体来说，我们评估 6 个维度：
- **规划质量**（20%）：Agent 的计划是否合理
- **战术决策**（20%）：每一步行动是否恰当
- **工具使用**（15%）：工具选择和参数是否正确
- **记忆保持**（15%）：关键信息是否被记住
- **重规划**（15%）：失败后是否有效调整
- **检索质量**（15%）：RAG 检索是否可靠、有无幻觉

---

## 二、核心技术难点与解决方案

### 2.1 难点一：LLM-as-Judge 的评分一致性问题

**问题描述**：用 LLM 当评委打分，最大的问题是"同一个轨迹，问两次可能打出不同的分"。这种不一致性会让评估结果不可信。

**我们的解决方案**：

#### 方案 A：显式评分锚点

我们在每个评估器的 prompt 中定义了 0/25/50/75/100 五个档位的具体行为描述。例如规划质量的"覆盖率"维度：

```
0 分：完全没有规划，或计划与目标毫无关系
25 分：仅覆盖了目标的 1-2 个方面，遗漏了超过一半的关键步骤
50 分：覆盖了主要步骤，但遗漏了 2-3 个关键里程碑
75 分：覆盖了绝大部分里程碑，仅遗漏 1 个次要步骤
100 分：完整覆盖所有必要里程碑，包括分析、实现、测试、文档
```

这样 LLM 就不是"凭感觉打分"，而是"对照锚点打分"。实测下来，评分一致性提升了约 30-50%。

#### 方案 B：多模型共识机制

我们用多个 LLM 独立评分，然后计算均值和标准差。标准差越小 = 一致性越高 = 评分越可信。

具体实现（`consensus.py`）：
- **三级优先级**：跨厂商共识（DeepSeek + GLM + Qwen）> 同厂商多模型（deepseek-chat + deepseek-reasoner）> 温度多样性（同模型 temp=0 vs 0.7）
- **自动降级**：检测哪些 API key 已配置，自动构建可用的 provider 列表
- **故障隔离**：单个 provider 失败返回 None，不影响其他 provider

```
DeepSeek Chat  ──→  Planning: 78  ─┐
GLM-4          ──→  Planning: 82  ─┤→ mean=80, std=2.0（一致性高=可信）
Qwen Plus      ──→  Planning: 80  ─┘
```

std < 2.0 表示高一致性，std > 10.0 表示模型间分歧大，可能需要优化评分标准。

#### 方案 C：Pydantic Structured Output

我们用 `with_structured_output` 强制 LLM 返回符合 Pydantic Schema 的结构化数据，而不是靠 prompt 约束 JSON 格式。

```python
# 之前：prompt 约束 JSON，可能返回非法值
chain = prompt | self.llm
response = await chain.ainvoke(inputs)
scores = self._parse_json_from_llm(response.content)  # 可能返回 101 分、-5 分

# 之后：Pydantic 强制约束
structured_llm = self.llm.with_structured_output(PlanningEvaluationResult)
chain = prompt | structured_llm
result = await self._invoke_structured_llm(chain, inputs, schema_class=PlanningEvaluationResult)
# PlanningEvaluationResult 有 ge=0, le=100 约束，不可能返回非法值
```

好处：
- 分数范围强制在 0-100（Pydantic `ge=0, le=100`）
- 校验失败时自动重试 3 次，把错误信息反馈给 LLM
- 解析失败不再静默返回默认 50 分

---

### 2.2 难点二：轨迹数据的 Token 爆炸问题

**问题描述**：一个 Agent 执行 200 步的轨迹，直接送给 LLM 评估会消耗 50k+ token，成本高且容易超出上下文窗口。

**解决方案：4 阶段确定性压缩管线**（`trajectory_compressor.py`）

这个压缩管线完全是确定性的（不调用 LLM），所以速度快且可复现：

```
原始轨迹（200 步）
    ↓ Stage 1: 重要性过滤
    保留 plan, tool_call, tool_result, memory_*, retrieval, evidence, failure, replan, think
    丢弃 node_execute, tool_decision, state_change 等噪声
    ↓ Stage 2: Think 截断
    think 步骤的 observation 截断到 200 字符（内部独白对评估价值低）
    ↓ Stage 3: 滑动窗口
    保留最近 30 步 + "锚点"步骤（plan, failure）
    锚点步骤永远保留——没有初始计划就无法评估规划质量，没有失败就无法评估重规划
    ↓ Stage 4: 格式化
    输出结构化文本，头部显示 total/omitted/showing 计数
    ↓
压缩后轨迹（~40 步，token 减少 80%）
```

**关键设计决策**：
- **锚点保留**：即使被窗口截断，`PLAN` 和 `FAILURE` 类型的步骤也永远保留。这是核心洞察——没有初始计划，Judge 无法评估规划质量；没有失败记录，Judge 无法评估重规划能力。
- **不可变操作**：`_copy_step_with` 创建浅拷贝而不是修改原始对象，防止副作用。

---

### 2.3 难点三：评估性能问题

**问题描述**：6 个评估器 × 3 个共识模型 = 18 次 LLM 调用，串行执行需要 3-5 分钟。

**解决方案：多层性能优化**

#### 优化 1：并行评估（5x 提速）

```python
# evaluate_parallel() — 6 个评估器并发
results = await asyncio.gather(
    planning_evaluator.evaluate(goal, trajectory),
    tactical_evaluator.evaluate(goal, trajectory),
    tool_use_evaluator.evaluate(goal, trajectory),
    memory_evaluator.evaluate(goal, trajectory),
    replan_evaluator.evaluate(goal, trajectory),
    retrieval_evaluator.evaluate(goal, trajectory),
)
```

从串行 ~71s 降到并行 ~15s。

#### 优化 2：LLM 结果缓存（10x+ 成本节省）

```python
# 缓存键 = 评估器名称 + 模型名 + prompt SHA-256 哈希
cache_key = f"llm:{evaluator_name}:{model_name}:{prompt_hash}"
```

相同轨迹 + 相同目标 = 相同评估结果，缓存 24 小时。这在迭代开发中特别有用——改了 prompt 后重跑评估，只有变化的维度会重新调用 LLM。

#### 优化 3：增量评估（3x 提速）

当 Agent 的 prompt 或工具配置变化时，不需要重跑所有 6 个评估器。

```python
# 变化-维度映射
CHANGE_DIMENSION_MAP = {
    "plan": ["planning", "tactical"],
    "tool_call": ["tool_use"],
    "retrieval": ["retrieval"],
    "memory_write": ["memory", "replan"],
}
```

通过 `DiffService` 对比两个轨迹的差异，只重跑受影响的维度，其余维度直接复用旧分数。通常节省 2/3 的评估时间。

#### 优化 4：Redis 缓存层（优雅降级）

```python
async def cache_get(key):
    try:
        return await redis.get(key)
    except Exception:
        return None  # Redis 不可用时静默降级，不崩溃
```

缓存策略：
- LLM 结果：24h TTL（最激进，因为相同输入 = 相同输出）
- 报表聚合：5min TTL
- Dashboard 计数器：30s TTL
- Task 查询：60s TTL

关键设计：**Redis 是可选依赖**，所有缓存操作 try/except 后静默返回 None/False，应用在没有 Redis 的情况下也能正常运行。

---

### 2.4 难点四：评估维度的适用性问题

**问题描述**：不是所有轨迹都涉及所有维度。如果 Agent 顺利完成任务没有触发重规划，"重规划"维度就不应该参与总分计算。

**解决方案：适用性自动标记 + 权重归一化**

```python
# ToolUseEvaluator：没有工具调用时标记不适用
if not tool_calls:
    return ToolUseScore(
        applicable=False,
        not_applicable_reason="轨迹中未包含工具调用，该维度已从综合评分中剔除。",
        ...
    )

# ReplanEvaluator：没有重规划且没有错过的时机时标记不适用
if not replan_events and not missed_opportunities:
    return ReplanScore(
        applicable=False,
        not_applicable_reason="Agent 顺利完成未触发重规划，该维度已从综合评分中剔除。",
        ...
    )
```

加权总分计算时，不适用的维度从分子和分母中同时剔除：

```python
def weighted_overall(dimension_results, weights):
    numerator = 0.0
    denominator = 0.0
    for dimension, weight in weights.items():
        if not is_applicable(dimension_results.get(dimension)):
            continue  # 跳过不适用的维度
        numerator += weight * score
        denominator += weight
    return numerator / denominator  # 权重自动归一化
```

---

### 2.5 难点五：评估结果的可解释性

**问题描述**：用户看到"Tool Use: 45 分"，不知道具体是哪里出了问题。

**解决方案：多层诊断信息**

每个评估器都返回结构化的诊断信息：

```python
class ToolUseEvaluationResult(BaseModel):
    selection_quality: int = Field(ge=0, le=100)
    parameter_accuracy: int = Field(ge=0, le=100)
    result_utilization: int = Field(ge=0, le=100)
    overall: int = Field(ge=0, le=100)
    feedback: str = Field(description="详细评估反馈")
    inefficient_calls: List[InefficientCall] = Field(default_factory=list)
    # InefficientCall 包含 tool, issue, suggestion
```

另外还有两个调试服务：
- **ReplayService**：逐步回放 Agent 的执行过程，展示每步的 LLM 原始 Prompt/Response/Model/Latency
- **JudgeService**：展示 LLM 裁判的原始 prompt 和 response，让用户看到"评委是怎么打分的"

---

### 2.6 难点六：回归检测

**问题描述**：迭代 Agent 时，需要知道某次改动是提升了还是降低了质量。

**解决方案：自动回归检测**（`regression_detection.py`）

```python
# 不同维度有不同的敏感度阈值
THRESHOLDS = {
    "overall": -5.0,      # 总分下降 5 分就触发
    "tool_use": -8.0,     # 工具使用下降 8 分触发
    "planning": -10.0,    # 其他维度下降 10 分触发
    ...
}

# 双重检测：总分下降 OR 任一维度大幅下降
has_regression = (overall_delta < overall_threshold) or any(d.is_regression for d in dims)
```

生成的人类可读报告：
```
Regression detected! Planning: 72->58 (-14). Overall: 75->68 (-7).
```

阈值可通过构造函数注入，CI 环境用更紧的阈值，开发环境用更松的。

---

## 三、架构设计决策

### 3.1 双执行模式

```python
if settings.EVAL_PARALLEL:
    # 默认：直接 asyncio.gather，并行执行 6 个评估器（~15s）
    return await evaluate_parallel(goal, trajectory)
else:
    # 调试：LangGraph StateGraph，串行执行（~71s），有完整 trace
    return await evaluation_graph.invoke({"goal": goal, "trajectory": trajectory})
```

并行模式是默认的，因为评估器之间没有依赖关系。串行模式用于调试和 trace。

### 3.2 幂等性设计

- `create_evaluation`：同一 task 的 IN_PROGRESS 评估已存在时，返回已有记录而不是创建重复
- `create_task`：提供 ID 时幂等（ID 已存在则返回已有记录）
- Stream claim：Redis SETNX 原子操作，防止并发评估同一任务

### 3.3 故障隔离

每个评估器独立 try-catch，一个维度失败不影响其他维度：

```python
async def _safe_evaluate(evaluator, goal, trajectory):
    try:
        return await evaluator.evaluate(goal, trajectory)
    except Exception as e:
        return zero_score_with_error(e)  # 返回零分 + 错误信息
```

---

## 四、数据模型：14 种 ActionType

轨迹由 14 种动作类型组成，每种有独立的 Pydantic Schema：

| ActionType | 用途 | Detail Schema |
|------------|------|---------------|
| `plan` | 初始计划 | `PlanDetail` (steps, milestones) |
| `plan_update` | 计划更新 | `PlanUpdateDetail` (next_action, remaining_steps) |
| `tool_call` | 工具调用 | `ToolCallDetail` (tool_name, input) |
| `tool_result` | 工具结果 | `ToolResultDetail` (success, error_type, duration_ms) |
| `memory_write` | 写记忆 | `MemoryWriteDetail` (key, value, memory_type) |
| `memory_read` | 读记忆 | `MemoryReadDetail` (key, hit, value) |
| `think` | 思考 | `ThinkDetail` (thought) |
| `replan` | 重规划 | `ReplanDetail` (reason, new_plan) |
| `failure` | 失败 | `FailureDetail` (error_type, error_message, recoverable) |
| `retrieval` | 知识检索 | `RetrievalDetail` (query, source, result_count, retrieved_docs) |
| `evidence` | 证据池 | `EvidenceDetail` (evidence_type, sources) |
| `state_change` | 状态变化 | `StateChangeDetail` (trigger, diff) |
| `node_execute` | 节点执行 | `NodeExecuteDetail` (node_name) |
| `tool_decision` | 工具决策 | `ToolDecisionDetail` |

SDK 在构造时通过 Pydantic `field_validator` 自动截断过长字段，构造即类型安全。

---

## 五、性能指标

| 指标 | 数值 | 说明 |
|------|------|------|
| 单次全评估耗时 | 15-30s | 6 评估器 asyncio.gather 并行 |
| 增量评估耗时 | 5-10s | 只重跑受影响的 2-3 个维度 |
| 轨迹压缩率 | ~80% | 200 步 → 40 步 |
| LLM 缓存命中率 | 24h 内重复评估 100% 命中 | 相同轨迹+目标=相同结果 |
| 多模型共识开销 | 3x | 3 个 provider 并行，耗时与单模型相当 |
| 综合分单调递减验证 | 93.1 → 20.0 | 人为劣化轨迹，分数单调下降 |
