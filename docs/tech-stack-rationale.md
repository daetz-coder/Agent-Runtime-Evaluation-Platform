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
