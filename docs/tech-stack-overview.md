# 技术栈全景分析

> 本文档梳理项目中所有技术组件的选型逻辑与使用方式，供面试准备与技术复盘参考。

---

## 技术栈总览

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend Layer                         │
│  Vue 3 + TypeScript + Element Plus + ECharts + Pinia        │
│  构建: Vite  │  通信: Axios + SSE                           │
├─────────────────────────────────────────────────────────────┤
│                      Backend Layer                          │
│  FastAPI + Pydantic v2 + Uvicorn (ASGI)                     │
│  异步: AsyncIO  │  ORM: SQLAlchemy 2.0 + Alembic            │
├─────────────────────────────────────────────────────────────┤
│                      AI / Agent Layer                       │
│  LangGraph (状态机编排) + LangChain (LLM 抽象)              │
│  评估器: 6 个 LLM-as-Judge  │  共识: 多模型交叉验证         │
├─────────────────────────────────────────────────────────────┤
│                      RAG / Search Layer                     │
│  Milvus (向量) + BM25 (关键词) + RRF 融合                   │
│  Embedding: bge-small-zh-v1.5  │  Rerank: bge-reranker-base │
│  Query Rewrite: 路由分类 + 指代消解 + 多策略改写             │
├─────────────────────────────────────────────────────────────┤
│                      Infrastructure Layer                   │
│  Docker (沙箱隔离) + Redis (缓存/限流/消息队列)              │
│  Celery (异步任务)  │  可观测: OpenTelemetry + Prometheus    │
├─────────────────────────────────────────────────────────────┤
│                      Quality Assurance                      │
│  pytest + Golden Test Suite + Monotonicity Benchmark         │
│  Ruff (lint) + mypy (type check) + Makefile (统一入口)       │
└─────────────────────────────────────────────────────────────┘
```

---

## 一、后端框架

### FastAPI

| 项目 | 说明 |
|------|------|
| 版本 | `>=0.109.0` |
| 角色 | 主 Web 框架，提供 REST API、SSE 流式推送、依赖注入、自动 OpenAPI 文档 |
| 选型理由 | Flask 同步会阻塞 LLM 调用；Django 太重（ORM/Admin 用不上）；Tornado 缺少类型校验和自动文档 |
| 关键优势 | 原生 async/await、Pydantic v2 集成减少 60% 手写校验代码、依赖注入适配多 LLM 厂商切换 |
| 文件引用 | `app/main.py:108`、`pyproject.toml:20` |

async/await 是基于事件循环（Event Loop）的协作式并发模型，通过 await 主动让出执行权，实现单线程下的高并发 IO 调度。

### Pydantic v2

| 项目 | 说明 |
|------|------|
| 版本 | `>=2.5.3` |
| 角色 | 数据校验、序列化、JSON Schema 生成，Rust 核心比 v1 快 5-50x |
| 选型理由 | Pydantic v1 性能瓶颈；dataclasses 无运行时校验；attrs 无 JSON Schema 自动生成 |
| 文件引用 | `app/core/config.py:8`、`app/models/schemas.py` |

在 Agent 系统中，JSON 只是数据交换格式，而 Pydantic 的序列化/校验过程本质是将不可信的结构化文本转换为类型安全的运行时对象，从而保证 Agent 多步调用链中的数据一致性与安全性。Rust core 的加速主要优化的是解析与校验的 CPU 密集型过程，而不是 JSON 本身。



### SQLAlchemy 2.0 + Alembic

| 项目 | 说明 |
|------|------|
| 版本 | SQLAlchemy `>=2.0.25`、Alembic `>=1.13.1` |
| 角色 | 异步 ORM，统一 SQLite/PostgreSQL 访问；Alembic 管理数据库迁移 |
| 设计 | 开发环境 SQLite 零配置；生产切 PostgreSQL 只需改连接串 |
| 文件引用 | `app/db/database.py`、`app/db/models.py` |

---

## 二、AI / Agent 框架

### LangGraph

| 项目 | 说明 |
|------|------|
| 版本 | `>=0.2.0` |
| 角色 | 核心 Agent 编排引擎，提供显式状态图、条件路由、并行执行、HITL 中断、检查点恢复 |
| 选型理由 | LangChain Agent=黑盒无审计；AutoGen=对话驱动、SDK 不稳定；CrewAI=无 HITL；自研=开发成本高、无调试工具 |
| 五大优势 | ① 显式可审计状态图 ② 原生 HITL（`interrupt()`）③ `Send()` API 并行评估 ④ 检查点恢复长评估 ⑤ 零成本集成 LangChain 生态 |
| 文件引用 | `app/graphs/evaluation_graph.py:392`、`app/agent_runtime/graph.py:205`、`sdk/adapters/langgraph.py:66` |

### LangChain

| 项目 | 说明 |
|------|------|
| 版本 | `>=0.3.0` |
| 角色 | LLM 抽象层，统一所有厂商接口（`BaseChatModel`、`BaseMessage`、`StructuredTool`） |
| 选型理由 | LiteLLM 无 Chain/Tool 抽象；直接调厂商 SDK 换模型改一堆代码；`ChatOpenAI` 覆盖所有 OpenAI 兼容 API |
| 文件引用 | `app/evaluators/base.py:21`、`app/agent_runtime/llm_factory.py:19` |

### 多模型共识机制

| 项目 | 说明 |
|------|------|
| 厂商 | DeepSeek（默认，性价比高）/ GLM-4（免费额度）/ Qwen-Plus（阿里云集成）/ GPT-4o（高质量）/ Claude（长上下文） |
| 机制 | 三厂商独立评分 → mean ± std 聚合，消除单一模型评估偏差 |
| 文件引用 | `app/evaluators/consensus.py:64`、`app/agent_runtime/llm_factory.py:19` |

---

## 三、检索系统（RAG）

### 四级检索 Pipeline

```
用户 Query
    │
    ▼
┌─────────────────┐
│ Query Rewrite    │  路由分类 → 指代消解 → 多策略改写 → 相似度校验
└────────┬────────┘
         │
    ▼────┴────▼
┌─────────┐ ┌─────────┐
│ Semantic │ │  BM25   │  双路并行检索
│ (Milvus) │ │ (jieba) │
└────┬────┘ └────┬────┘
     │            │
     ▼────────────▼
┌─────────────────┐
│   RRF 融合       │  k=60，倒数秩融合消除分数尺度差异
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Cross-Encoder    │  bge-reranker-base 精排
│   Rerank         │
└────────┬────────┘
         │
         ▼
      Top-K 结果
```

### Milvus

| 项目 | 说明 |
|------|------|
| 角色 | 向量数据库，存储文档 embedding，支持 COSINE 相似度搜索 |
| 选型理由 | Chroma 大规模不稳定；FAISS 无元数据过滤/持久化；Pinecone 仅云服务、国内访问受限；Weaviate 部署太重 |
| 设计 | 开发用 Milvus Lite（单文件零配置），生产切 Milvus Server 只需改 URI |
| 文件引用 | `app/wiki_agent/agent/tools/vector_store.py:30` |

### Embedding: bge-small-zh-v1.5

| 项目 | 说明 |
|------|------|
| 维度 | 512 维 |
| 特点 | 中文 MTEB 排名靠前、本地推理零 API 成本 |
| 选型理由 | bge-large 内存 2x、速度慢 2-3x；text2vec-large-chinese 不维护；OpenAI embedding 有 API 成本且国内受限 |
| 文件引用 | `app/wiki_agent/agent/tools/embeddings.py:19`、`app/wiki_agent/config.py:26` |

### BM25 + RRF 融合

| 项目 | 说明 |
|------|------|
| BM25 | jieba 中文分词 + BM25Okapi 倒排索引，处理精确关键词匹配（函数名、API 名） |
| RRF | 倒数秩融合 `1/(k+rank+1)`，零参数消除语义/关键词分数尺度差异 |
| 文件引用 | `app/wiki_agent/agent/tools/bm25_index.py:87`、`app/wiki_agent/agent/tools/search_tools.py:79` |

### Reranker: bge-reranker-base

| 项目 | 说明 |
|------|------|
| 角色 | Cross-Encoder 精排，在 RRF 融合后对候选文档二次排序 |
| 选型理由 | Cross-encoder 精度 > bi-encoder；bge-reranker-large 3x 慢、精度提升边际小；Cohere Rerank 有 API 成本 |
| 文件引用 | `app/wiki_agent/agent/tools/reranker.py:100` |

### Query Rewrite Pipeline

| 阶段 | 说明 |
|------|------|
| 路由分类 | LLM 轻量 4 分类：direct / simple / complex / ambiguous |
| 指代消解 | 代词检测 + LLM 上下文补齐（多轮对话场景） |
| 策略改写 | Multi-Query / HyDE / Decompose，按分类结果路由 |
| 相似度校验 | cosine ≥ 0.7 才通过，低于阈值回退原始 query 防止语义漂移 |
| 文件引用 | `app/wiki_agent/agent/tools/query_rewriter.py` |

---

## 四、前端

### Vue 3 + TypeScript

| 项目 | 说明 |
|------|------|
| 框架 | Vue 3 Composition API + `<script setup>` |
| 类型 | TypeScript strict mode |
| 选型理由 | React 无官方状态管理/路由；Angular 太重；Svelte 生态不成熟 |
| 文件引用 | `frontend/src/main.ts`、`frontend/tsconfig.json` |

### UI 与可视化

| 组件 | 角色 | 选型理由 |
|------|------|---------|
| Element Plus | 表单/表格/对话框等 UI 组件 | Vue 3 最成熟的 UI 库，中文文档完善 |
| ECharts | 雷达图/趋势图/热力图/分布图 | 图表类型丰富（雷达、热力图），中文文档好；Chart.js 缺雷达/热力图，D3 太底层 |
| Pinia | 状态管理 | Vue 3 官方推荐，替代 Vuex |
| Vite | 构建工具 | 原生 ESM、毫秒级 HMR；Webpack 配置复杂、HMR 慢 |

### 实时通信

| 方式 | 用途 |
|------|------|
| SSE (Server-Sent Events) | 评估进度实时推送、Benchmark 流式结果 |
| Axios | REST API 通信，拦截器处理鉴权和错误 |

---

## 五、基础设施

### Docker

| 用途 | 说明 |
|------|------|
| 部署 | 容器化后端应用，`docker-compose.yml` 一键启动 Redis + Backend + Frontend |
| 沙箱隔离 | Agent 代码在独立容器中执行，CPU/内存/网络限制，防止恶意代码 |
| 文件引用 | `Dockerfile`、`docker-compose.yml`、`app/agent_runtime/sandbox/executor.py` |

### Redis

| 用途 | 说明 |
|------|------|
| LLM 缓存 | 24h TTL，避免重复调用 |
| 报告缓存 | 5min TTL，聚合结果 |
| Celery Broker | 消息队列 |
| API 限流 | Sorted Set 滑动窗口 |
| 降级设计 | Redis 不可用时所有操作静默返回 None/False，核心功能不受影响 |
| 文件引用 | `app/core/cache.py` |

### Celery

| 项目 | 说明 |
|------|------|
| 角色 | 分布式任务队列，异步执行评估任务 |
| 特性 | 指数退避重试、并发控制、队列分离（evaluation vs sandbox）、死信追踪 |
| 选型理由 | asyncio 单进程崩溃丢任务；RQ 太简单；Dramatiq 社区小 |
| 文件引用 | `app/celery_app.py` |

---

## 六、可观测性

### OpenTelemetry

| 项目 | 说明 |
|------|------|
| 角色 | 分布式追踪，Span 树覆盖完整评估链路 |
| 链路 | sandbox → session acquire → workspace → agent loop → LLM call → tool → trajectory → evaluation |
| 选型理由 | CNCF 标准无厂商锁定；自托管 Jaeger 数据不出境 |
| 文件引用 | `app/core/tracing.py:47` |

### Prometheus

| 项目 | 说明 |
|------|------|
| 角色 | 指标采集，`/metrics` 端点暴露 |
| 指标 | 评估次数/耗时、LLM 调用延迟/token、沙箱会话池、工具调用次数、HTTP 请求（共 12 项） |
| 文件引用 | `app/core/metrics.py`、`app/api/metrics_middleware.py` |

### structlog

| 项目 | 说明 |
|------|------|
| 角色 | 结构化日志，生产 JSON 输出，开发彩色控制台 |
| 特性 | 自动注入 correlation ID（`X-Request-ID`），全链路日志串联 |
| 文件引用 | `app/core/logging.py:53` |

---

## 七、测试与质量保障

### 测试体系

| 层次 | 工具 | 说明 |
|------|------|------|
| 单元测试 | pytest + pytest-asyncio | `asyncio_mode = "auto"`，24 个测试文件 |
| 覆盖率 | pytest-cov | `--cov=app --cov-report=term-missing` |
| 回归测试 | Golden Test Suite | 4 条黄金轨迹 + 预期分数范围，保障评估器迭代不引入回归 |
| 单调性基准 | Monotonicity Benchmark | 6 条不同质量轨迹，验证评分随质量单调递减 |
| CI 门禁 | `run_ci_gate.py` | 两阶段：Golden Suite → Monotonicity Check |

### 代码质量

| 工具 | 角色 |
|------|------|
| Ruff | Linter + Formatter，Rust 实现，100x 快于 flake8 |
| mypy | 静态类型检查，strict mode |
| Makefile | 统一开发者入口：`make lint`、`make test`、`make golden`、`make check-ci` |

---

## 八、自研 SDK

| 项目 | 说明 |
|------|------|
| 角色 | 零侵入轨迹采集，外部 Agent 一行代码接入评估平台 |
| 三种模式 | ① `instrument_langgraph()` 透明包装 ② `create_proxy_llm()` LLM 代理 ③ `create_callback_handler()` LangChain 回调 |
| 特性 | 14 种 Action Type、线程安全缓冲、指数退避重试、批量上传、进程内传输模式 |
| 文件引用 | `sdk/collector.py`、`sdk/adapters/langgraph.py` |

---

## 九、选型方法论

项目在 `docs/tech-stack-rationale.md` 中记录了每个选型的决策过程，遵循统一的四步法：

```
1. 明确约束 → 2. 列出候选 → 3. 多维对比 → 4. 记录决策
```

### 示例：LangGraph 选型

| 步骤 | 内容 |
|------|------|
| 约束 | 显式状态图、HITL 中断、并行评估、检查点恢复、LangChain 生态兼容 |
| 候选 | LangGraph / LangChain Agent / AutoGen / CrewAI / 自研状态机 |
| 对比 | LangChain Agent=黑盒无审计；AutoGen=对话驱动、SDK 不稳定；CrewAI=无 HITL；自研=开发成本高无调试工具 |
| 决策 | LangGraph 满足全部 5 个约束，且与 LangChain 零成本集成 |

### 示例：Milvus 选型

| 候选 | 淘汰原因 |
|------|---------|
| Chroma | 大规模不稳定 |
| FAISS | 无元数据过滤、无持久化 |
| Pinecone | 仅云服务、国内访问受限 |
| Weaviate | 部署太重 |
| **Milvus Lite** | 本地单文件零配置，生产可无缝升级 Milvus Server |

---

## 十、关键设计原则

1. **可选降级**：Redis、Celery、Docker 任何一个挂掉，核心功能不受影响（cache miss 回源、task 同步执行、sandbox 降级为进程内执行）

2. **渐进式复杂度**：SQLite → PostgreSQL、Milvus Lite → Milvus Server、单模型 → 多模型共识，每个组件都支持从简单到复杂的平滑升级

3. **生态一致性**：LangGraph + LangChain + LangChain-OpenAI 共享 `BaseChatModel`、`BaseMessage`、`StructuredTool` 等同一套抽象，避免适配层胶水代码

4. **可观测优先**：OpenTelemetry span 树覆盖完整评估链路，Prometheus 12 项指标 + structlog 结构化日志，任何环节出问题都能定位
