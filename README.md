# Agent Runtime Evaluation Platform

<p align="center">
  <b>AI Agent 运行时全维度质量评估平台</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.14-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.115+-059F00?logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/Vue_3-v3.5+-4FC08D?logo=vuedotfiles" alt="Vue 3">
  <img src="https://img.shields.io/badge/LangGraph-v0.3+-3399FF?logo=langchain" alt="LangGraph">
  <img src="https://img.shields.io/badge/SQLAlchemy-async-FF6B6B?logo=sqlalchemy" alt="SQLAlchemy Async">
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License">
</p>

对 Agent 的 **规划、战术决策、工具使用、记忆保持、重规划、RAG 检索质量** 六个维度进行量化评估。基于 LangGraph 编排、LLM-as-Judge 评分、FastAPI + Vue3 全栈交付。

## 项目定位

```
❌ 不是 Prompt Evaluation（市场饱和）
✅ Agent Runtime Evaluation（评估 Agent 运行时的行为质量）
```

评估 Agent 在真实任务中每一步的决策质量，而非仅看最终结果。

## 🛠️ 技术栈一览

| 类别 | 技术 | 用途 |
|------|------|------|
| **后端框架** | FastAPI + Uvicorn | REST API + SSE 实时流，全异步 |
| **Agent 编排** | LangGraph + LangChain | Agent ReAct 循环、评估工作流 |
| **AI 模型** | DeepSeek / GLM / Qwen / OpenAI | LLM 推理 + LLM-as-Judge 评估裁判 |
| **向量检索** | Milvus Lite + FAISS + BM25 | RAG 知识库混合检索（向量+关键词） |
| **数据库** | SQLAlchemy Async + SQLite / PostgreSQL | 持久化存储，Alembic 迁移管理 |
| **缓存** | Redis（可选，优雅降级） | LLM 响应缓存、报表聚合、接口限流 |
| **前端** | Vue 3 + TypeScript + Element Plus + ECharts | 管理面板与可视化图表 |
| **容器** | Docker（Sandbox 执行环境） | 安全隔离的 Agent 运行沙箱 |
| **可观测性** | OpenTelemetry + Prometheus + structlog | 链路追踪、指标监控、结构化日志 |
| **任务队列** | Celery（可选，优雅降级） | 异步评估任务，指数退避重试 |
| **数据科学** | sentence-transformers + CrossEncoder | 检索结果 ReRank 重排序 |
| **SDK** | Python SDK（httpx + langchain-core） | 零侵入轨迹采集，三种集成模式 |

## 🔑 关键特性

| 特性 | 说明 |
|------|------|
| **双模评测** | Sandbox 自动化评测 / 外部 SDK 埋点轨迹评测 |
| **6 维评分体系** | Planning / Tactical / Tool Use / Memory / Replan / Retrieval |
| **多模型共识** | 跨厂商（DeepSeek + GLM + Qwen）独立评分，输出均值 ± 标准差 |
| **增量评估** | Trajectory Diff 检测变化维度，只重算受影响项，节省 2/3 时间 |
| **回归检测** | 自动对比基线分数，发现退化维度 |
| **Replay 调试器** | 回放 Agent 每步 LLM 原始 Prompt/Response |
| **Judge 透明面板** | 公开每个维度的评分依据（原始 Judge Prompt/Response） |
| **Trajectory Diff** | 步骤级对比两次 Agent 运行差异 |
| **SSE 流式评测** | 实时推送 Agent 执行步骤 + 评估进度 |
| **LLM 响应缓存** | Redis 缓存 LLM 调用，按模型名隔离，多模型共识不串缓存 |
| **RAG 知识库** | Milvus + BM25 混合检索 + BGE ReRank 的 Wiki Agent |
| **Golden Test Suite** | 4 条黄金轨迹保障评估器修改不引入回归 |
| **OpenTelemetry** | 全链路 Span 树，支持 Jaeger/Zipkin 可视化 |
| **优雅降级** | Redis/Celery/Docker 不可用时均自动降级，核心功能不受影响 |

## 核心指标（实测）

| 指标 | 数值 |
|------|------|
| 评估维度 × 子指标 | 6 × 3~4 = **20 项** |
| 轨迹动作类型 | **14 种** (plan / tool_call / replan / retrieval …) |
| 接入模式 | **3 种** (LangGraph Instrument / LLM Proxy / Callback) |
| 多轨迹单调性验证 | **93.1 → 92.0 → 81.0 → 54.4 → 27.8 → 20.0** |
| 单次全评估耗时 | **15~30s** (6 评估器并行) |
| 单次成本 (DeepSeek) | **¥0.012** （GPT-4o 的 1/27） |
| 检索基准 (Wiki-Agent) | Semantic Top-1: 85%, MRR: 0.91 |

*数据来源: `tests/benchmark_*.py` 和 `tests/eval_*.py`，真实 LLM 调用。*

## 系统架构

```
┌──────────────────────────────────────────────────────────────────┐
│                Frontend (Vue 3 + Element Plus + ECharts)          │
│  Dashboard · Tasks · Evaluations · Analytics · Wiki Agent        │
│  雷达图 · 趋势线 · 热力图 · Replay 调试器 · Judge 透明面板       │
└──────────────────────────┬───────────────────────────────────────┘
                           │ REST API
┌──────────────────────────┴───────────────────────────────────────┐
│                    Backend (FastAPI)                              │
│  CorrelationIdMiddleware → AuthMiddleware → RateLimitMiddleware  │
│  → PrometheusMiddleware → CORS                                   │
│                                                                  │
│  ┌─────────────────────┐  ┌──────────────────────────────────┐  │
│  │ Agent Runtime        │  │ Parallel Evaluation (6 Evals)    │  │
│  │ (Agent in Sandbox)   │  │ planning · tactical · tool_use   │  │
│  │ AgentRunner          │  │ memory · replan · retrieval      │  │
│  │ LangGraph ReAct Loop │  │ LLM-as-Judge + 幻觉检测          │  │
│  │ ToolProxy (5 tools)  │  │ + _invoke_llm_cached()           │  │
│  │ SessionPool (Docker) │  └──────────────────────────────────┘  │
│  │ WorkspaceManager     │                                        │
│  └─────────┬───────────┘  ┌──────────────────────────────────┐  │
│            │               │ Service Layer                     │  │
│            ▼               │ EvaluationService · ReplayService │  │
│  ┌───────────────────┐    │ DiffService · JudgeService        │  │
│  │ Docker Sandbox    │    │ IncrementalEvalService            │  │
│  │ /workspace (rw)   │    │ RegressionDetectionService        │  │
│  │ network=none      │    │ QuotaService · WebhookService     │  │
│  │ read_only root    │    └──────────────────────────────────┘  │
│  └───────────────────┘                                          │
├──────────────────────────────────────────────────────────────────┤
│  Redis Cache (可选) · SQLite/PostgreSQL · Alembic Migrations    │
│  Celery Task Queue · OpenTelemetry Tracing · Prometheus Metrics │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  SDK (零侵入接入)                                                 │
│  instrument_langgraph() · create_proxy_llm()                     │
│  create_callback_handler()                                        │
└──────────────────────────────────────────────────────────────────┘
```

## 📊 效果展示

### 评估仪表盘（Dashboard）

| 视图 | 内容 | 用途 |
|------|------|------|
| **统计卡片** | 总评估数、平均分、最高/最低维度、评估趋势 | 快速掌握整体质量 |
| **雷达图** | 6 维度综合能力全景展示 | 一眼识别短板维度 |
| **趋势折线** | 各维度分数随时间变化（按天/周聚合） | 跟踪改进效果/发现退化 |
| **维度对比柱状图** | 各维度均分 ± 标准差对比 | 横向对比能力分布 |
| **最近任务列表** | 最近 5 条评估记录 | 快速切入详情 |
| **主要问题** | 分数最低的维度 + 典型反馈 | 定位改进方向 |

### 评估详情页（Evaluation Detail）

| 视图 | 内容 | 用途 |
|------|------|------|
| **综合得分** | 加权总分（大号数字展示）+ 质量等级标签 | 一目了然 |
| **6 维评分卡** | 每维度分数 + 子指标得分 + LLM 反馈 | 逐项审查 |
| **雷达图** | 该次评估的 6 维能力形状 | 直观对比 |
| **Trajectory 时间线** | 逐步骤回放 Agent 行为（action_type/工具调用/LLM思考） | 还原执行过程 |
| **Replay 调试器** | 展开每步查看 LLM 原始 Prompt + Response | 调试 Agent 行为 |
| **Judge 透明面板** | 选择维度 → 查看 Judge 原始 Prompt + Response | 验证评分合理性 |
| **多模型对比** | Consensus 模式下各厂商评分横向对比 | 评估结果可信度判断 |

### 数据分析页面（Analytics）

| 视图 | 内容 | 用途 |
|------|------|------|
| **得分分布图** | 各分数段的评估计数直方图 | 评估整体质量分布 |
| **维度趋势对比** | 多维度在同一时间轴的折线叠加 | 发现关联退化 |
| **相关性热力图** | 6 维度两两相关性矩阵 | 发现评估维度间的冗余/独立 |
| **性能热力图** | 评估耗时 × 模型 × 维度的热力图 | 发现性能瓶颈 |
| **智能洞察** | 自动识别"持续改进"/"需关注"/"退化中"维度 | 辅助决策 |
| **改进建议** | 基于低分维度的 LLM 生成建议列表 | 可操作反馈 |

### 系统设置页面（Settings）

| 视图 | 内容 | 用途 |
|------|------|------|
| **系统状态** | Redis / Milvus / 数据库 / ReRank 运行状态 + 标签 | 健康监控 |
| **评估配置** | 批量大小、并行开关、超时、是否自动评估 | 运行时控制 |
| **知识库统计** | 知识页数、向量分块、BM25 分块 | Wiki Agent 状态 |
| **环境信息** | 环境变量、版本号、许可信息 | 运维支持 |

### 评分质量标定

```
优秀 ≥ 80  ·  良好 ≥ 60  ·  一般 ≥ 40  ·  较差 < 40

颜色映射:
  ┌─────────────────────────────────────────────────────┐
  │  0──────20──────40──────60──────80──────100        │
  │  🔴 较差    🟠 一般    🟡 良好    🟢 优秀         │
  └─────────────────────────────────────────────────────┘
```

### Consensus 多模型评分效果

```
deepseek-chat:     78 │████████████████████████████   78
glm-4:             82 │██████████████████████████████ 82
qwen-plus:         75 │██████████████████████████     75
─────────────────────────────────────────────────────
综合均分: 78.3  ·  分歧度 (std): 2.9  ·  一致性: 较高
```

当 `std < 5` 时评分可信度高，`std > 15` 时需人工复核。

## 快速开始

本项目包含两个子项目，**一条命令同时启动**：

| 子项目 | 地址 |
|--------|------|
| **Agent Evaluation Platform** | `http://localhost:3000` |
| **Wiki-Agent** | `http://localhost:3000/wiki-agent` |
| **API 文档 (Swagger)** | `http://localhost:8000/docs` |

### 1. 环境配置

```bash
# 克隆项目
git clone https://github.com/daetz-coder/Agent-Runtime-Evaluation-Platform.git
cd Agent-Runtime-Evaluation-Platform

# 复制环境变量配置
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY
# 其他 LLM 可选: OPENAI_API_KEY / ANTHROPIC_API_KEY
```

### 2. 安装依赖

```bash
# 后端依赖（含 Wiki-Agent）
pip install -e ".[dev]"

# 前端依赖
cd frontend && npm install && cd ..
```

### 3. 启动服务

**方式一：命令行（推荐）**

```bash
# 终端 1: 启动后端（Mock 模式，无需 Docker）
SANDBOX_MOCK_MODE=true python -m app.main
# → 后端运行在 http://localhost:8000

# 终端 2: 启动前端
cd frontend && npm run dev
# → 前端运行在 http://localhost:3000
```

**方式二：Windows 一键启动**

```bash
start.bat
# 自动打开两个窗口，分别启动后端和前端
```

**方式三：Docker Compose**

```bash
cp .env.example .env   # 填入 DEEPSEEK_API_KEY
docker compose up --build
# 前端 http://localhost:3000  后端 http://localhost:8000
```

### 4. 验证

```bash
# 健康检查
curl http://localhost:8000/health
# → 健康检查响应示例:
# {
#   "status": "healthy",
#   "app": "Agent Evaluation Platform",
#   "version": "0.1.0",
#   "database": "connected",
#   "sandbox": "ready",
#   "wiki": "initialized"
# }

# 运行示例评估
python example_evaluation.py

# 运行基准测试
python -m tests.benchmark_score_distribution
python -m tests.eval_retrieval_standalone
```

## 六维评估体系

| 维度 | 子指标（权重） | 评估器 |
|------|---------------|--------|
| **Planning** | coverage(0.30), ordering(0.20), granularity(0.20), completeness(0.30) | `planning_evaluator.py` |
| **Tactical** | relevance(0.35), efficiency(0.30), correctness(0.35) | `tactical_evaluator.py` |
| **Tool Use** | selection_quality(0.40), parameter_accuracy(0.30), result_utilization(0.30) | `tool_use_evaluator.py` |
| **Memory** | retention(0.45), relevance(0.30), consistency(0.25) | `memory_evaluator.py` |
| **Replan** | trigger_appropriateness(0.35), adaptation_quality(0.35), learning_from_failure(0.30) | `replan_evaluator.py` |
| **Retrieval** | relevance(0.35), evidence_accuracy(0.35), coverage(0.30) + hallucination_detected | `retrieval_evaluator.py` |

加权聚合: Planning 0.20 + Tactical 0.20 + Tool Use 0.15 + Memory 0.15 + Replan 0.15 + Retrieval 0.15

质量标定: 优秀 ≥80 · 良好 ≥60 · 一般 ≥40 · 较差 <40

## 三种接入模式（零侵入 SDK）

外部项目只需 `pip install httpx langchain-core` 即可使用：

```python
# 方式 1: LangGraph Instrument
from sdk import instrument_langgraph
graph = instrument_langgraph(build_graph())

# 方式 2: LLM Proxy
from sdk import create_proxy_llm
llm = create_proxy_llm(ChatOpenAI(...))

# 方式 3: LangChain Callback
from sdk import create_callback_handler
llm = ChatOpenAI(callbacks=[create_callback_handler()])
```

SDK 收集器特性: 线程安全 · 批量上传 · 失败回退 · 离线模式 · 14 种动作类型 · 状态 diff

## 项目结构

```
├── app/
│   ├── agent_runtime/       # Agent in Sandbox — 沙箱内运行 Agent
│   │   ├── runner.py        #   AgentRunner 编排器
│   │   ├── graph.py         #   LangGraph ReAct 循环
│   │   ├── prompts/         #   版本化 prompt 模板 (v1.1.yaml)
│   │   ├── tools/           #   5 个沙箱工具 (python/bash/file_*)
│   │   ├── sandbox/         #   SessionPool + WorkspaceManager
│   │   ├── mock_executor.py #   Mock 模式（无需 Docker）
│   │   ├── llm_factory.py   #   多 LLM provider 工厂
│   │   └── trajectory_recorder.py  # 轨迹记录器
│   ├── evaluators/          # 6 个评估器 + BaseEvaluator + Consensus
│   ├── graphs/              # LangGraph 评估工作流 + 并行评估
│   ├── services/            # 业务逻辑层
│   │   ├── evaluation_service.py    # 评估编排
│   │   ├── replay_service.py        # Replay 调试器
│   │   ├── judge_service.py         # Judge 透明度
│   │   ├── diff_service.py          # Trajectory Diff
│   │   ├── incremental_eval.py      # 增量评估
│   │   ├── regression_detection.py  # 回归检测
│   │   ├── quota.py                 # 资源配额
│   │   └── webhook.py               # Webhook 通知（指数退避重试）
│   ├── core/                # 基础设施
│   │   ├── config.py        #   pydantic-settings 配置
│   │   ├── cache.py         #   Redis 缓存层
│   │   ├── tracing.py       #   OpenTelemetry 链路追踪
│   │   ├── logging.py       #   structlog 结构化日志
│   │   └── metrics.py       #   Prometheus 指标
│   ├── api/                 # REST API + 中间件
│   │   ├── v1/endpoints/    #   tasks / evaluation / reports / benchmark / system
│   │   ├── auth_middleware.py
│   │   ├── rate_limit_middleware.py
│   │   ├── correlation_id_middleware.py
│   │   ├── metrics_middleware.py
│   │   └── workspace.py     #   Workspace 隔离
│   ├── celery_app.py        # Celery 任务队列
│   ├── models/              # Pydantic schemas + ActionType
│   ├── db/                  # SQLAlchemy ORM + async session
│   ├── wiki_agent/          # Wiki-Agent（RAG + 自动评估）
│   └── main.py              # FastAPI 入口
├── sdk/                     # 独立 SDK 包（零 app 依赖）
├── alembic/                 # 数据库迁移
├── frontend/                # Vue 3 + Element Plus + ECharts
├── tests/                   # 207 个测试
├── Makefile                 # make lint / test / golden / run
├── pyproject.toml
└── README.md
```

## API 接口

```http
# Agent in Sandbox（推荐）
POST   /api/v1/evaluations/run                   # 沙箱评估（Agent 在 Docker 中运行）
POST   /api/v1/evaluations/run/stream             # SSE 流式沙箱评估
POST   /api/v1/evaluations/run-legacy              # 一步式评估（提交 goal+轨迹，直接返回分数）

# 传统评估流程
POST   /api/v1/tasks/                              # 创建任务
GET    /api/v1/tasks/                              # 列出任务（支持 ?skip=&limit=）
GET    /api/v1/tasks/dashboard                     # 仪表板统计
GET    /api/v1/tasks/{id}                          # 获取任务
PUT    /api/v1/tasks/{id}                          # 更新任务
DELETE /api/v1/tasks/{id}                          # 删除任务
POST   /api/v1/tasks/{id}/trajectory               # 上传轨迹（deprecated → 使用 /run）
GET    /api/v1/tasks/{id}/trajectory               # 获取轨迹
POST   /api/v1/evaluations/                        # 运行评估（异步，支持 use_stream）
POST   /api/v1/evaluations/stream                  # SSE 流式评估进度
POST   /api/v1/evaluations/quick                   # 同步评估（阻塞，返回完整结果）
POST   /api/v1/evaluations/batch                   # 批量评估
POST   /api/v1/evaluations/consensus               # 多模型共识评估
GET    /api/v1/evaluations/                        # 列出评估
GET    /api/v1/evaluations/{id}                    # 获取评估详情
DELETE /api/v1/evaluations/{id}                    # 删除评估记录

# 高级评估
GET    /api/v1/evaluations/{id}/replay             # Replay 调试器
GET    /api/v1/evaluations/{id}/judge-raw[/{dim}]  # Judge 透明度
GET    /api/v1/evaluations/diff                    # Trajectory 对比
POST   /api/v1/evaluations/incremental             # 增量评估
GET    /api/v1/evaluations/regression/check        # 回归检测

# 报告
GET    /api/v1/reports/summary                     # 评估摘要（含六维 AVG）
GET    /api/v1/reports/trends                      # 评估趋势
GET    /api/v1/reports/tasks/{task_id}/history     # 某任务的所有评估历史
GET    /api/v1/reports/compare/{task_id}           # 迭代对比
GET    /api/v1/reports/export/{task_id}            # 导出 Markdown 报告
GET    /api/v1/reports/dimensions/{dim}            # 维度统计

# 基准
GET    /api/v1/benchmark/monotonicity              # 单调性基准元数据
POST   /api/v1/benchmark/monotonicity/run          # SSE 实时跑单调性基准

# 运维
GET    /api/v1/system/health                       # 健康检查
GET    /api/v1/system/metrics                      # Prometheus 指标
GET    /api/v1/evaluations/settings                 # 评估运行时配置
GET    /api/v1/settings/prompts                    # Prompt 模板版本列表
GET    /api/v1/settings/prompts/{version}          # 获取指定 Prompt 版本内容
PUT    /api/v1/settings/prompts/{version}          # 创建/更新 Prompt 版本

# Wiki Agent 知识库
GET    /api/wiki/tree                              # 知识库目录树
GET    /api/wiki/page/{path}                       # 获取页面内容
POST   /api/wiki/page/{path}                       # 创建/更新页面
PUT    /api/wiki/page/{path}                       # 更新页面
DELETE /api/wiki/page/{path}                       # 删除页面
POST   /api/wiki/page/{path}/rollback              # Git 回滚
GET    /api/wiki/history                           # 版本历史
GET    /api/wiki/search?q=                         # 搜索知识库
POST   /api/wiki/import                            # 导入 Markdown
POST   /api/wiki/auto-tag                          # LLM 自动生成标签
GET    /api/wiki/export                            # 知识库 ZIP 导出
GET    /api/wiki/vector-stats                      # 向量数据库统计
POST   /api/chat/stream                            # SSE 流式对话
POST   /api/chat/message                           # 同步对话
POST   /api/chat/confirm                           # HITL CRUD 确认
POST   /api/chat/save-knowledge                    # 保存对话为知识
POST   /api/chat/sessions                          # 创建对话会话
GET    /api/chat/sessions                          # 列出对话会话
GET    /api/chat/sessions/{session_id}             # 获取对话会话历史
DELETE /api/chat/sessions/{session_id}             # 删除对话会话
```

## 开发者体验

### Debug 工具

| 工具 | 说明 | 使用方式 |
|------|------|----------|
| **Replay 调试器** | 查看 Agent 每步 LLM 原始输入/输出 | `GET /evaluations/{id}/replay` 或前端点击"Replay 调试器" |
| **Judge 透明面板** | 查看每个维度的评分理由（原始 prompt + response） | `GET /evaluations/{id}/judge-raw/{dim}` 或前端面板 |
| **Trajectory Diff** | 对比两次 Agent 运行的步骤差异 | `GET /evaluations/diff?base_evaluation_id=...&head_evaluation_id=...` |
| **Mock 模式** | 无需 Docker 即可运行 Agent Runtime | `SANDBOX_MOCK_MODE=true` 环境变量 |

### 开发提速

| 功能 | 说明 |
|------|------|
| **增量评估** | 修改 prompt 后只重算受影响维度，节省 2/3 时间 |
| **Golden Test Suite** | 4 条黄金轨迹验证 evaluator 修改不引入回归，`make golden` |
| **回归检测** | 自动发现分数退化，`GET /evaluations/regression/check` |
| **版本追踪** | 每个 Evaluation 记录 prompt/model/provider 版本 |
| **Makefile** | `make lint` / `make test` / `make golden` / `make check-ci` |

## 技术栈

**后端**: Python 3.11+ · FastAPI · LangGraph · LangChain · SQLAlchemy (async) · Pydantic · httpx

**可观测性**: OpenTelemetry (链路追踪) · Prometheus (指标) · structlog (结构化日志 + Correlation ID)

**任务队列**: Celery + Redis (评估任务重试、并发控制)

**缓存**: Redis (可选，优雅降级) — 报表聚合缓存 · LLM 结果缓存 · 接口限流 · 会话缓存

**数据库**: SQLite (开发) · PostgreSQL (生产) · Alembic 迁移

**沙箱**: Docker (隔离容器，network=none，read_only root，writable /workspace)

**前端**: Vue 3 · TypeScript · Vite · Element Plus · ECharts

**LLM**: DeepSeek (默认) · OpenAI · Anthropic · ZhipuAI · Qwen (可切换)
