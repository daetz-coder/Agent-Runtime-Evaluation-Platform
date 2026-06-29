# Agent Runtime Evaluation Platform

AI Agent 运行时全维度质量评估平台。对 Agent 的规划、战术决策、工具使用、记忆保持、重规划、RAG 检索质量六个维度进行量化评估。基于 LangGraph 编排、LLM-as-Judge 评分、FastAPI + Vue 3 全栈交付。

> 评估 Agent 在真实任务中每一步的决策质量，而非仅看最终结果。
> 这不是 Prompt Evaluation 工具，而是 Agent Runtime Evaluation 平台。

---

- [快速开始](#快速开始)
- [系统架构](#系统架构)
- [评估体系](#评估体系)
- [功能特性](#功能特性)
- [API 概览](#api-概览)
- [项目结构](#项目结构)
- [相关文档](#相关文档)

---

## 快速开始

最小化启动步骤：

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

访问 http://localhost:3000 查看仪表盘，访问 http://localhost:8000/docs 查看 API 文档。

详细安装与配置说明见 [快速开始指南](docs/getting_started.md)。

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
| **Agent 运行时** | 在 Docker 沙箱中运行 Agent，自动采集执行轨迹 |
| **评估引擎** | 6 个并行 LLM-as-Judge 评估器，对轨迹进行多维度评分 |
| **Wiki Agent** | 基于 RAG 的知识库问答 Agent，形成"运行-评估-改进"闭环 |

详细架构说明见 [架构文档](docs/architecture.md)，设计思路见 [设计文档](docs/design.md)。

---

## 评估体系

| 维度 | 权重 | 关注点 |
|------|------|--------|
| 规划质量 (Planning) | 20% | 里程碑覆盖、步骤顺序、粒度、完整性 |
| 战术决策 (Tactical) | 20% | 下一步行动的相关性、效率、正确性 |
| 工具使用 (Tool Use) | 15% | 工具选择、参数准确性、结果利用 |
| 记忆保持 (Memory) | 15% | 关键事实保持、回忆相关性、一致性 |
| 重规划 (Replan) | 15% | 触发时机、适应质量、从失败中学习 |
| 检索质量 (Retrieval) | 15% | 文档相关性、证据准确性、信息覆盖度 |

质量等级：优秀 ≥ 80 · 良好 ≥ 60 · 一般 ≥ 40 · 较差 < 40

评估器实现细节见 [evaluators/](../app/evaluators/) ，评分模型定义见 [schemas.py](../app/models/schemas.py)。

---

## 功能特性

- **双模评测**：Sandbox 自动化评测 / 外部 SDK 埋点轨迹评测
- **多模型共识**：跨厂商（DeepSeek + GLM + Qwen）独立评分，输出均值与标准差
- **增量评估**：轨迹 diff 检测变化维度，只重算受影响项，节省约 2/3 时间
- **回归检测**：自动对比基线分数，发现退化维度
- **SSE 流式评测**：实时推送 Agent 执行步骤与评估进度
- **Replay 调试器**：回放 Agent 每步 LLM 原始 Prompt/Response
- **Judge 透明面板**：公开每个维度的评分依据
- **Trajectory Diff**：步骤级对比两次 Agent 运行差异
- **Wiki Agent**：基于 Milvus + BM25 混合检索的 RAG 知识库问答系统
- **多 LLM 支持**：DeepSeek / GLM / Qwen / OpenAI / Anthropic 可切换
- **可选依赖**：Redis / Celery / Docker 不可用时均自动降级

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

完整 API 参考见 [API 文档](docs/api.md)。

---

## 项目结构

```
├── app/                    # 后端应用
│   ├── agent_runtime/      # Agent 沙箱运行时
│   ├── evaluators/         # 6 个评估器 + 共识评估 + 评分工具
│   ├── graphs/             # LangGraph 评估工作流
│   ├── services/           # 业务逻辑层
│   ├── core/               # 基础设施（配置/缓存/日志/链路追踪）
│   ├── api/                # REST API + 中间件
│   ├── wiki_agent/         # Wiki Agent 子系统
│   ├── models/             # Pydantic schema 定义
│   └── db/                 # SQLAlchemy ORM + 迁移
├── frontend/               # Vue 3 前端
├── sdk/                    # 独立 SDK 包（外部项目集成用）
├── tests/                  # 测试用例
└── docs/                   # 文档
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
| [SDK 使用指南](docs/adapters.md) | SDK 集成方式、LangGraph/LangChain/手动模式 |
| [端口配置](docs/ports.md) | 服务端口、常用地址、一键启动 |
| [前端文档](frontend/README.md) | Vue 3 前端技术栈、页面功能说明 |
| [OpenAPI 规范](http://localhost:8000/docs) | Swagger UI 交互式文档 |
