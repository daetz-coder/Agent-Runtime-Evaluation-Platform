# Agent Runtime Evaluation Platform

AI Agent 运行时质量评估平台 — 对 Agent 的规划、战术决策、工具使用、记忆保持、重规划、RAG 检索质量六个维度进行量化评估。基于 LangGraph 编排、LLM-as-Judge 评分、FastAPI + Vue3 全栈交付。

## 项目定位

```
❌ 不是 Prompt Evaluation（市场饱和）
✅ Agent Runtime Evaluation（评估 Agent 运行时的行为质量）
```

评估 Agent 在真实任务中每一步的决策质量，而非仅看最终结果。

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
┌─────────────────────────────────────────────────────┐
│              Frontend (Vue 3 + ECharts)              │
│  Dashboard / Tasks / Evaluations / Analytics / Wiki Agent / 向量管理  │
│  雷达图 · 趋势线 · 热力图 · 相关性矩阵               │
└──────────────────────┬──────────────────────────────┘
                       │ REST API
┌──────────────────────┴──────────────────────────────┐
│              Backend (FastAPI)                       │
│  api/v1/endpoints/  →  services/  →  graphs/        │
│  tasks · evaluation · reports · benchmark │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────┐
│        Parallel Evaluation (6 Evaluators)            │
│  planning · tactical · tool_use · memory              │
│          · replan · retrieval → aggregate            │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────┐
│  SQLite / PostgreSQL · TrajectoryCollector           │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  SDK (零侵入接入)                                     │
│  instrument_langgraph() · create_proxy_llm()         │
│  create_callback_handler()                            │
│  外部项目: pip install httpx && export PYTHONPATH=.  │
└─────────────────────────────────────────────────────┘
```

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
# 终端 1: 启动后端（自动初始化 Milvus + BM25 索引）
python -m app.main
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
# → {"status":"healthy","app":"Agent Evaluation Platform","version":"0.1.0"}

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
│   ├── evaluators/       # 6 个评估器 + BaseEvaluator + Consensus
│   ├── graphs/           # LangGraph 评估工作流 + 并行评估
│   ├── adapters/         # SDK 重导出（兼容层）
│   ├── collectors/       # 轨迹收集器（SDK 重导出）
│   ├── api/v1/endpoints/ # REST API (tasks/evaluation/reports)
│   ├── services/         # EvaluationService 业务逻辑
│   ├── models/           # Pydantic schemas + ActionType 常量
│   ├── db/               # SQLAlchemy ORM + async session
│   ├── core/             # pydantic-settings 配置
│   ├── wiki_agent/       # 集成 Wiki-Agent（RAG + 自动评估）
│   └── main.py           # FastAPI 入口
├── sdk/                  # 独立 SDK 包（零 app 依赖）
│   ├── collector.py      # 轻量级轨迹收集器
│   └── adapters/         # 三个 Adapter
├── frontend/             # Vue 3 + Element Plus + ECharts
├── tests/                # 评估脚本 + 单元测试 + 集成测试
├── example/              # 示例 + 简历
├── pyproject.toml
└── README.md
```

## API 接口

```http
POST   /api/v1/tasks/                     # 创建任务
GET    /api/v1/tasks/{id}                 # 获取任务
POST   /api/v1/tasks/{id}/trajectory      # 上传轨迹
POST   /api/v1/evaluations/               # 运行评估（异步，支持 use_stream）
POST   /api/v1/evaluations/stream         # SSE 流式评估进度
GET    /api/v1/evaluations/{id}           # 获取评估结果
GET    /api/v1/benchmark/monotonicity     # 单调性基准元数据
POST   /api/v1/benchmark/monotonicity/run # SSE 实时跑单调性基准
GET    /api/v1/reports/summary            # 评估摘要（含六维 AVG）
GET    /api/v1/reports/trends             # 评估趋势
GET    /api/v1/reports/compare/{task_id}  # 迭代对比
GET    /api/v1/reports/export/{task_id}   # 导出 Markdown 报告
GET    /api/v1/reports/dimensions/{dim}   # 维度统计
```

## 技术栈

**后端**: Python 3.11+ · FastAPI · LangGraph · LangChain · SQLAlchemy (async) · Pydantic · httpx

**前端**: Vue 3 · TypeScript · Vite · Element Plus · ECharts

**LLM**: DeepSeek (默认) · OpenAI · Anthropic (可切换)

**数据库**: SQLite (开发) · PostgreSQL (生产)
