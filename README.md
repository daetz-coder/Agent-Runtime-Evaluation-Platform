# Agent Runtime Evaluation Platform

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)
![Vue 3](https://img.shields.io/badge/Vue_3-v3.5-4FC08D?logo=vuedotjs&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-v0.3-1C3C5C?logo=langchain&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-v5.7-3178C6?logo=typescript&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7.2-DC382D?logo=redis&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-FF6B6B?logo=sqlalchemy&logoColor=white)
![Milvus](https://img.shields.io/badge/Milvus-2.4-00A98F)
![ECharts](https://img.shields.io/badge/ECharts-5.5-AA344D)
![License](https://img.shields.io/badge/License-MIT-yellow)

</div>

**AI Agent 运行时全维度质量评估平台。** 对 Agent 的规划、战术决策、工具使用、记忆保持、重规划、RAG 检索质量六个维度进行量化评估。基于 LangGraph 编排、LLM-as-Judge 评分、FastAPI + Vue 3 全栈交付。

> **❌ 不是 Prompt Evaluation**（评估最终输出文本质量）
> **✅ 是 Agent Runtime Evaluation**（评估 Agent 运行时每一步的决策质量）

---

## 快速开始

```bash
# 1. 安装依赖
pip install -e ".[dev]"
cd frontend && npm install && cd ..

# 2. 配置 API Key（编辑 .env，填入 DEEPSEEK_API_KEY）

# 3. 启动后端
python -m app.main

# 4. 另一个终端启动前端
cd frontend && npm run dev
```

访问 http://localhost:3000 查看仪表盘，http://localhost:8000/docs 查看 API 文档。

---

## 核心指标

| 指标 | 数值 |
|------|------|
| 评估维度 × 子指标 | 6 × 3~4 = 20 项 |
| 轨迹动作类型 | 14 种（Pydantic Schema 约束） |
| SDK 接入模式 | 3 种（Instrument / Proxy / Callback） |
| 单次全评估耗时 | 15~30s（6 评估器 asyncio.gather 并行） |
| 检索基准（Wiki Agent） | Top-1: **75%**, MRR: **0.825** |
| 综合分单调递减验证 | **93.1 → 20.0** |

---

## 功能演示

### 评估流程

![评估流程演示](https://daetz-image.oss-cn-hangzhou.aliyuncs.com/img/20260707163207267.gif)

展示一次 Agent 评估的完整过程：从触发评估到 6 个维度并行评分完成。

### 评估详情

![评估详情总览页](https://daetz-image.oss-cn-hangzhou.aliyuncs.com/img/20260707141239977.png)

评估详情总览：总分约 57 分，包含规划质量、战术决策、工具使用、记忆保持、重规划、检索质量等维度评分。

![检索质量评估页](https://daetz-image.oss-cn-hangzhou.aliyuncs.com/img/20260707141341679.png)

多模型共识与检索质量分析：4 个模型独立评分，指出检索相关性低、证据准确性不足等问题。

![另一组评估详情页](https://daetz-image.oss-cn-hangzhou.aliyuncs.com/img/20260707161942546.png)

另一组评估结果：总分约 60 分，战术决策较高，但检索质量为 0，工具使用和重规划不适用。

### Wiki Agent

![Wiki Agent 对话页](https://daetz-image.oss-cn-hangzhou.aliyuncs.com/img/20260707161942546.png)

Wiki Agent 对话页：用户询问 SWE-bench，系统回答后提示发现可保存知识，并生成知识保存卡片。

![HITL 流程演示](https://daetz-image.oss-cn-hangzhou.aliyuncs.com/img/20260707163244703.gif)

HITL（Human-in-the-Loop）机制：当 AI 决定创建或修改知识库条目时，会暂停并等待用户确认。

![知识保存提示页](https://daetz-image.oss-cn-hangzhou.aliyuncs.com/img/20260707125501320.png)

知识保存提示：系统提示 AI 发现可保存的新知识"模型上下文协议（MCP）"，并提供查看详情、确认保存、忽略操作。

![知识保存成功提示](https://daetz-image.oss-cn-hangzhou.aliyuncs.com/img/20260707162300669.png)

知识保存成功：界面显示"模型上下文协议（MCP）已保存到知识库"。

![变更流页面](https://daetz-image.oss-cn-hangzhou.aliyuncs.com/img/20260707125635924.png)

变更流页面：Wiki Agent 的变更流界面，展示已创建知识及文件路径和版本信息。

![MCP 知识详情页](https://daetz-image.oss-cn-hangzhou.aliyuncs.com/img/20260707125651205.png)

MCP 知识详情页：知识库中打开"模型上下文协议（MCP）"文档，展示定义、重要性和核心概念。

![LangChain 架构知识页](https://daetz-image.oss-cn-hangzhou.aliyuncs.com/img/20260707162237029.png)

LangChain 架构知识页：知识库中展示 LangChain 架构概述、RAG Agent 数据流以及与 LangGraph、CrewAI 的关系。

![Milvus 向量管理页](https://daetz-image.oss-cn-hangzhou.aliyuncs.com/img/20260707153600473.png)

Milvus 向量管理页：展示向量库管理界面，包括集合名、URI、维度、分块总数、页面数和分块列表。

### 系统管理

![系统概览演示](https://daetz-image.oss-cn-hangzhou.aliyuncs.com/img/20260707163220968.gif)

系统检查器：展示系统运行状态，包括 Sessions、Messages、Checkpoints、BM25 Chunks、Vectors 等统计信息。

---

## 评估体系

| 维度 | 权重 | 子指标 | 评估器 |
|------|------|--------|--------|
| 规划质量（Planning） | 20% | 覆盖率、顺序性、粒度、完整性 | `planning_evaluator.py` |
| 战术决策（Tactical） | 20% | 相关性、效率、正确性 | `tactical_evaluator.py` |
| 工具使用（Tool Use） | 15% | 选择质量、参数准确性、结果利用 | `tool_use_evaluator.py` |
| 记忆保持（Memory） | 15% | 保持力、相关性、一致性 | `memory_evaluator.py` |
| 重规划（Replan） | 15% | 触发适当性、适应质量、学习能力 | `replan_evaluator.py` |
| 检索质量（Retrieval） | 15% | 相关性、证据准确性、覆盖度 + 幻觉检测 | `retrieval_evaluator.py` |

- 质量等级：优秀 ≥ 80 · 良好 ≥ 60 · 一般 ≥ 40 · 较差 < 40
- 维度不适用时自动标记并从加权总分中剔除（权重重新归一化）

---

## 系统架构

```
┌─────────────┐     ┌───────────────────┐     ┌──────────────────┐
│   Frontend  │────▶│   FastAPI Server   │◀────│   SDK Collector  │
│  (Vue 3 +   │◀────│  (Async 全链路)    │     │  (Pydantic Schema)│
│   ECharts)  │     │                   │     └──────────────────┘
└─────────────┘     ├───────────────────┤
                    │   Evaluators × 6  │
                    │   (LLM-as-Judge)  │
                    ├───────────────────┤     ┌──────────────────┐
                    │   Redis Cache     │     │   SQLite / PG    │
                    │   (可选，优雅降级) │     │   (任务/轨迹/评估)│
                    └───────────────────┘     └──────────────────┘
```

两个核心子系统：

| 子系统 | 说明 |
|--------|------|
| **评估引擎** | 6 个并行 LLM-as-Judge 评估器 + 多模型共识 + 4 阶段轨迹压缩 |
| **Wiki Agent** | RAG 知识库问答（四级混合检索 + Query 改写 + 双层记忆 + HITL CRUD） |

---

## 关键特性

| 特性 | 说明 |
|------|------|
| **Pydantic Schema SDK** | 14 种 ActionType 各有独立 Pydantic 模型，field\_validator 自动截断，构造即类型安全 |
| **6 维评估体系** | 20 项子指标，含幻觉检测，适用性自动标记 |
| **多模型共识** | DeepSeek / GLM-4 / Qwen-Plus 独立评分 → 均值 ± 标准差，跨模型一致性量化 |
| **4 阶段轨迹压缩** | 重要性过滤 → Think 截断 → 滑动窗口 → 格式化，降低 LLM token 消耗 |
| **SSE 流式评估** | 实时推送评估进度，支持批量 / 增量 / 回归检测 |
| **增量评估** | Trajectory Diff 检测变化维度，只重算受影响项，节省约 2/3 时间 |
| **回归检测** | 自动对比基线分数，发现退化维度并告警 |
| **Replay 调试器** | 回放每步 LLM 原始 Prompt / Response / Model / Latency |
| **全链路 Async** | FastAPI + SQLAlchemy + Redis 全异步，sync I/O 通过 asyncio.to\_thread 桥接 |
| **优雅降级** | Redis / Celery 不可用时自动降级，核心功能不受影响 |

---

## 技术栈

| 类别 | 技术 | 用途 |
|------|------|------|
| 后端框架 | FastAPI + Uvicorn | REST API + SSE 实时流，全异步 |
| Agent 编排 | LangGraph + LangChain | Agent 状态图、评估工作流 |
| AI 模型 | DeepSeek / GLM / Qwen / OpenAI | LLM 推理 + LLM-as-Judge 评估裁判 |
| 向量检索 | Milvus + BM25 + RRF + Cross-Encoder | 四级混合检索 |
| 数据库 | SQLAlchemy Async + SQLite / PostgreSQL | 持久化存储，Alembic 迁移 |
| 缓存 | Redis（可选，优雅降级） | LLM 响应缓存、报表聚合、限流 |
| 任务队列 | Celery（可选，优雅降级） | 异步评估任务，指数退避重试 |
| 前端 | Vue 3 + TypeScript + Element Plus + ECharts | 管理面板与可视化图表 |
| SDK | Python SDK（Pydantic + httpx） | 零侵入轨迹采集，3 种接入模式 |

---

## 接入方式

```python
# LangGraph 项目 — 一行接入
from sdk import instrument_langgraph
graph = instrument_langgraph(build_graph())

# LangChain 项目 — 替换 LLM 创建
from sdk import create_proxy_llm
llm = create_proxy_llm(ChatOpenAI(model="gpt-4"))

# 任意项目 — 手动记录
from sdk.collector import get_collector
collector = get_collector()
collector.start("任务目标", context={...})
collector.record_tool_call("search", input={...}, output=result)
collector.finish(auto_run=True)
```

---

## 项目结构

```
app/                        # 后端应用
├── evaluators/             # 6 个评估器 + 共识评估 + 轨迹压缩 + 评分工具
├── graphs/                 # LangGraph 评估工作流（串行 / 并行 / 增量）
├── services/               # 业务逻辑层（evaluation / replay / judge / diff）
├── core/                   # 基础设施（config / cache / tracing / logging / metrics）
├── api/                    # REST API + 中间件（rate_limit / correlation_id）
├── wiki_agent/             # Wiki Agent（RAG 检索 / 对话 / 记忆 / 知识库管理）
├── models/                 # Pydantic schema 定义
└── db/                     # SQLAlchemy ORM + Alembic 迁移

frontend/                   # Vue 3 前端（dashboard / evaluations / analytics / wiki）
sdk/                        # 独立 SDK 包（Pydantic Schema + 3 种 Adapter + 手动记录）
scripts/                    # 基准测试脚本（benchmark / 检索评估）
tests/                      # pytest 单元测试与 Golden Test Suite
docs/                       # 文档
```

---

## 相关文档

| 文档 | 内容 |
|------|------|
| [架构文档](docs/architecture.md) | 系统架构、组件说明、数据流 |
| [API 文档](docs/api.md) | 全部 REST 端点、请求/响应示例、SSE 事件类型 |
| [SDK 文档](sdk/README.md) | 轨迹采集 SDK API、14 种 ActionType、容错机制 |
| [开发者指南](docs/developer_guide.md) | 本地开发、调试工具、版本追踪 |
| [前端文档](frontend/README.md) | Vue 3 前端技术栈、页面功能说明 |
