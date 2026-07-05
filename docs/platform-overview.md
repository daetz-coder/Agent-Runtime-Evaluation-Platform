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
