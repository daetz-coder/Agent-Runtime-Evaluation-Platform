# Agent Runtime Evaluation Platform

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.14-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.115+-059F00?logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/Vue_3-v3.5+-4FC08D?logo=vuedotfiles" alt="Vue 3">
  <img src="https://img.shields.io/badge/LangGraph-v0.3+-3399FF?logo=langchain" alt="LangGraph">
  <img src="https://img.shields.io/badge/SQLAlchemy-async-FF6B6B?logo=sqlalchemy" alt="SQLAlchemy Async">
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License">
</p>

AI Agent 运行时全维度质量评估平台。对 Agent 的规划、战术决策、工具使用、记忆保持、重规划、RAG 检索质量六个维度进行量化评估。基于 LangGraph 编排、LLM-as-Judge 评分、FastAPI + Vue 3 全栈交付。

## 项目定位

```
❌ 不是 Prompt Evaluation（评估 Agent 最终输出文本质量）
✅ Agent Runtime Evaluation（评估 Agent 运行时的行为质量）
```

评估 Agent 在真实任务中每一步的决策质量，而非仅看最终结果。覆盖 14 种轨迹动作类型（plan / tool_call / replan / retrieval / think / memory_write / failure 等），对每一步进行独立评分。

---

- [快速开始](#快速开始)
- [技术栈](#技术栈)
- [关键特性](#关键特性)
- [核心指标](#核心指标)
- [系统架构](#系统架构)
- [评估体系](#评估体系)
- [API 概览](#api-概览)
- [项目结构](#项目结构)
- [相关文档](#相关文档)

---

## 快速开始

```bash
# 1. 安装依赖
pip install -e ".[dev]"
cd frontend && npm install && cd ..

# 2. 配置 API Key（编辑 .env，填入 DEEPSEEK_API_KEY）

# 3. Mock 模式启动（无需 Docker）
SANDBOX_MOCK_MODE=true python -m app.main

# 4. 另一个终端启动前端
cd frontend && npm run dev
```

访问 http://localhost:3000 查看仪表盘，http://localhost:8000/docs 查看 API 文档。

> 详细安装与配置说明见 [快速开始指南](docs/getting_started.md)。支持 Windows `start.bat` 一键启动、Docker Compose 部署、以及 PostgreSQL 生产部署。

---

## 技术栈

| 类别 | 技术 | 用途 |
|------|------|------|
| 后端框架 | FastAPI + Uvicorn | REST API + SSE 实时流，全异步 |
| Agent 编排 | LangGraph + LangChain | Agent ReAct 循环、评估工作流 |
| AI 模型 | DeepSeek / GLM / Qwen / OpenAI / Anthropic | LLM 推理 + LLM-as-Judge 评估裁判 |
| 向量检索 | Milvus Lite + FAISS + BM25 | RAG 知识库混合检索（向量 + 关键词） |
| 数据库 | SQLAlchemy Async + SQLite / PostgreSQL | 持久化存储，Alembic 迁移管理 |
| 缓存 | Redis（可选，优雅降级） | LLM 响应缓存、报表聚合、接口限流 |
| 前端 | Vue 3 + TypeScript + Element Plus + ECharts | 管理面板与可视化图表 |
| 容器 | Docker（Sandbox 执行环境） | 安全隔离的 Agent 运行沙箱 |
| 可观测性 | OpenTelemetry + Prometheus + structlog | 链路追踪、指标监控、结构化日志 |
| 任务队列 | Celery（可选，优雅降级） | 异步评估任务，指数退避重试 |
| SDK | Python SDK（httpx + langchain-core） | 零侵入轨迹采集，三种集成模式 |

---

## 关键特性

| 特性 | 说明 |
|------|------|
| **双模评测** | Sandbox 自动化评测 / 外部 SDK 埋点轨迹评测 |
| **6 维评分体系** | Planning / Tactical / Tool Use / Memory / Replan / Retrieval，含 20 项子指标 |
| **适用性标记** | 维度不适用时自动标记并从综合评分剔除（如无工具调用时 Tool Use 标记为 N/A） |
| **多模型共识** | 跨厂商（DeepSeek + GLM + Qwen）独立评分，LLM 缓存按模型名隔离 |
| **增量评估** | Trajectory Diff 检测变化维度，只重算受影响项，节省约 2/3 时间 |
| **回归检测** | 自动对比基线分数，发现退化维度并告警 |
| **SSE 流式评测** | 实时推送 Agent 执行步骤 + 6 维评估进度 |
| **Replay 调试器** | 回放 Agent 每步 LLM 原始 Prompt / Response / Model / Latency |
| **Judge 透明面板** | 公开每个维度的评分依据（原始 Judge Prompt / Response 可查） |
| **LLM 生成建议** | 改进建议由 LLM 基于具体错误场景生成，非硬编码模板 |
| **Trajectory Diff** | 步骤级对比两次 Agent 运行差异（added / removed / changed） |
| **Golden Test Suite** | 4 条黄金轨迹 + 预期分数范围，保障评估器修改不引入回归 |
| **Wiki Agent** | 基于 Milvus + BM25 混合检索 + BGE ReRank 的 RAG 知识库问答系统 |
| **OpenTelemetry** | 全链路 Span 树，支持导出到 Jaeger / Zipkin 可视化 |
| **优雅降级** | Redis / Celery / Docker 不可用时均自动降级，核心功能不受影响 |

---

## 核心指标

| 指标 | 数值 |
|------|------|
| 评估维度 × 子指标 | 6 × 3~4 = 20 项 |
| 轨迹动作类型 | 14 种（plan / tool_call / replan / retrieval / think / memory_write / failure 等） |
| 接入模式 | 3 种（LangGraph Instrument / LLM Proxy / Callback） |
| 单次全评估耗时 | 15~30s（6 评估器并行 asyncio.gather） |
| 单次成本（DeepSeek） | ¥0.012（GPT-4o 的 1/27） |
| 检索基准（Wiki Agent） | Semantic Top-1: 85%, MRR: 0.91 |

> 以上数据来源 `tests/benchmark_*.py` 和 `tests/eval_*.py`，基于真实 LLM 调用。

---

## 系统架构

```
Frontend (Vue 3) ──REST/SSE──▶ Backend (FastAPI) ──▶ Docker Sandbox
                                    │
                              ┌─────┴─────┐
                              │           │
                         Redis Cache   6 Evaluators
                        (可选降级)    (LLM-as-Judge)
                              │           │
                              └─────┬─────┘
                                    │
                              ┌─────┴─────┐
                              │  Database  │
                              │ SQLite/PG  │
                              └───────────┘
```

平台包含三个核心子系统：

| 子系统 | 说明 |
|--------|------|
| **Agent Runtime** | 在 Docker 沙箱中运行 Agent，自动采集执行轨迹 |
| **评估引擎** | 6 个并行 LLM-as-Judge 评估器，对轨迹进行多维度评分 |
| **Wiki Agent** | 基于 RAG 的知识库问答 Agent，形成"运行-评估-改进"闭环 |

> 详细架构说明见 [架构文档](docs/architecture.md)，设计思路见 [设计文档](docs/design.md)。

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
- 评估器实现见 `app/evaluators/`，评分模型定义见 `app/models/schemas.py`

---

## API 概览

| 分组 | 前缀 | 主要功能 |
|------|------|----------|
| 评估 | `/api/v1/evaluations/` | 创建评估、流式评估、共识评估、增量评估、批量评估 |
| 任务 | `/api/v1/tasks/` | 任务 CRUD、轨迹提交 |
| 报告 | `/api/v1/reports/` | 评分摘要、趋势分析、维度统计、迭代对比 |
| 基准 | `/api/v1/benchmark/` | 单调性基准测试 |
| 运维 | `/api/v1/system/` | 健康检查、Prometheus 指标 |
| 知识库 | `/api/wiki/*` | 页面 CRUD、搜索、自动标签、ZIP 导出 |
| 对话 | `/api/chat/*` | SSE 流式对话、HITL 确认、会话管理 |

> 完整 API 参考见 [API 文档](docs/api.md)，包含请求/响应示例、SSE 事件类型。

---

## 项目结构

```
app/                        # 后端应用
├── agent_runtime/          # Agent 沙箱运行时（runner / graph / tools / sandbox）
├── evaluators/             # 6 个评估器 + 共识评估 + 评分工具
├── graphs/                 # LangGraph 评估工作流（串行 / 并行 / 增量）
├── services/               # 业务逻辑层（evaluation / replay / judge / diff / incremental）
├── core/                   # 基础设施（config / cache / tracing / logging / metrics）
├── api/                    # REST API + 中间件（auth / rate_limit / correlation_id）
├── wiki_agent/             # Wiki Agent 子系统（RAG 检索 / 对话 / 知识库管理）
├── models/                 # Pydantic schema 定义
└── db/                     # SQLAlchemy ORM + Alembic 迁移

frontend/                   # Vue 3 前端（dashboard / evaluations / analytics / wiki）
sdk/                        # 独立 SDK 包（外部项目零侵入集成）
tests/                      # 测试用例（单元测试 / 基准测试 / Golden Test Suite）
docs/                       # 文档
```

---

## 相关文档

| 文档 | 内容 |
|------|------|
| [快速开始指南](docs/getting_started.md) | 环境要求、安装步骤、启动方式、配置参考 |
| [架构文档](docs/architecture.md) | 系统架构、组件说明、数据流、可观测性 |
| [设计文档](docs/design.md) | 设计思路、评估体系、缓存策略、关键要点 |
| [开发者指南](docs/developer_guide.md) | 本地开发、调试工具、CI 门禁、版本追踪 |
| [API 文档](docs/api.md) | 全部 REST 端点、请求/响应示例、SSE 事件类型 |
| [SDK 集成指南](docs/adapters.md) | SDK 三种集成方式、配置选项、工作原理 |
| [端口配置](docs/ports.md) | 服务端口、常用地址、一键启动 |
| [项目约定](docs/conventions.md) | 编码规范、Git 流程、开发命令参考 |
| [前端文档](frontend/README.md) | Vue 3 前端技术栈、页面功能说明 |
| [SDK 文档](sdk/README.md) | 轨迹采集 SDK API、14 种 Action Type、容错机制 |
