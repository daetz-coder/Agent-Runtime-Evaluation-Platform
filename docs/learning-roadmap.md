# 学习路线图 — AI Agent 基础设施平台岗

## 你的当前状态 vs JD 要求

| JD 要求 | 你已有的 | 差距 |
|---------|---------|------|
| LangGraph / LangChain | ✅ 深度使用（6 评估器 + 4-Node Agent） | — |
| Tool Calling | ✅ Wiki Agent CRUD Tools | — |
| Human-in-the-Loop | ✅ LangGraph interrupt + Checkpoint | — |
| RAG / 向量检索 | ✅ Milvus + BM25 + BGE-M3 + RRF | — |
| LLM-as-a-Judge | ✅ 六维评估 + Consensus 多模型 | — |
| Prompt Engineering | ✅ 6 个 Evaluator Prompt Template | — |
| MCP 协议 | ❌ 完全没接触 | 🔴 必学 |
| A2A (Agent-to-Agent) | ❌ 没涉及 | 🔴 必学 |
| Agent 运行沙箱 | ❌ 没涉及 | 🟡 |
| Redis / 消息队列 | ❌ 项目中未使用 | 🟡 |
| 分布式系统 | ❌ 单机部署为主 | 🟡 |
| 微服务 / Nacos / 灰度发布 | ❌ 无 | 🟠 |
| Spring AI / Alibaba | ❌ Java 技术栈 | 🟠 |
| 微调 (Fine-tuning) | ❌ 无 | 🟢 |

---

## 学习路线（按优先级）

### 🔴 Tier 1 — 必学（2-4 周）

#### 1. MCP 协议（Model Context Protocol）
- **为什么**: JD 明确提到，Agent 工程 2025-2026 最热门协议
- **是什么**: Anthropic 发布的 Agent-Tool 通信标准协议，类似 LSP 之于 IDE
- **学什么**:
  - MCP Server / Client 架构：`stdio` 和 `streamable-http` 两种 transport
  - 如何写一个 MCP Server（Python SDK: `mcp`）
  - 如何让 LangGraph Agent 通过 MCP Client 调用外部工具
- **项目落地**: 把你现有的 Wiki Agent CRUD Tools 封装成 MCP Server，然后用 MCP Client 调用
- **简历写法**: 「基于 MCP 协议实现 Agent-Tool 标准化通信，支持 stdio/HTTP 双模式」

#### 2. A2A 协议（Agent-to-Agent / Multi-Agent）
- **为什么**: JD 明确提到，企业级 Agent 平台核心
- **是什么**: Google 发布的 Agent 间通信协议
- **学什么**:
  - Multi-Agent 协作模式：Supervisor / Swarm / Hierarchical
  - LangGraph 的 `Send` API 实现多 Agent 并行
  - Agent 间共享 State / Memory 的设计模式
- **项目落地**: 在评估平台中新增 Multi-Agent 评估场景（两个 Agent 协作完成任务）
- **简历写法**: 「设计 Multi-Agent 协作评估体系，支持 Supervisor/Swarm 两种编排模式」

---

### 🟡 Tier 2 — 强推（2-4 周）

#### 3. Redis + 消息队列
- **为什么要学**: 分布式系统基础，JD 明确要求
- **学什么**:
  - Redis 基础：String/Hash/List/Set/Sorted Set + Pub/Sub
  - 消息队列：Redis Stream / RabbitMQ / Kafka 基础概念
  - 异步任务队列：Celery / ARQ
- **项目落地**: 把评估任务从 FastAPI BackgroundTasks 迁移到 Redis Queue，支持分布式 Worker
- **简历写法**: 「基于 Redis Queue 实现分布式评估任务调度，支持多 Worker 并行」

#### 4. Agent 运行沙箱
- **为什么**: JD 提到，Agent 安全执行的基础设施
- **学什么**:
  - Docker SDK for Python：动态创建/销毁容器
  - 沙箱隔离：网络隔离、文件系统隔离、资源限制（cgroups）
  - 超时控制、代码执行结果收集
- **项目落地**: 为评估平台增加沙箱执行模式（Agent 在 Docker 容器中运行，轨迹自动收集）
- **简历写法**: 「实现 Agent 运行沙箱，Docker 容器隔离 + 资源限制 + 轨迹自动采集」

---

### 🔵 Tier 3 — 进阶（学到就是赚到）

#### 5. 分布式系统基础
- 分布式锁（Redis RedLock）
- 配置中心（Nacos / Consul）
- 服务发现与注册
- API 网关（Kong / Traefik）
- 分布式链路追踪（OpenTelemetry — 你的 pyproject.toml 里已有，但没真的用起来）

#### 6. 微调（Fine-tuning）基础
- LoRA / QLoRA 概念
- 用你的评估平台生成训练数据（好 trajectory vs 差 trajectory）
- 微调一个小模型（Qwen2.5-0.5B）做特定领域评估

---

## 推荐学习顺序

```
Week 1-2: MCP 协议
  → 把 Wiki Agent Tools 封装成 MCP Server
  → 用 MCP Client 调用

Week 3-4: A2A / Multi-Agent
  → LangGraph Send API
  → 两 Agent 协作评估场景

Week 5-6: Redis + 消息队列
  → 评估任务队列化
  → 分布式 Worker

Week 7-8: Agent 沙箱
  → Docker SDK
  → 隔离执行 + 轨迹收集
```

---

## 可以立刻开始做的（零学习成本）

- 把项目中已有的 `OpenTelemetry` 配置真正跑起来（pyproject.toml 里有依赖但没用）
- 给项目加 GitHub Actions CI（跑 pytest + ruff + mypy）
- 写 `docs/mcp-a2a-plan.md` — 设计如何在现有平台中集成 MCP + A2A

---

## 面试可以讲的「故事线」

1. **从 5 维到 6 维**：怎么发现 RAG 评估缺口 → 设计 RetrievalEvaluator → 幻觉检测 → 前端诊断面板
2. **从串行到并行**：71s → 15s，asyncio.gather + LangGraph 隔离 → 性能优化思维
3. **从单模型到多模型共识**：LLM Judge 不稳定怎么办 → DeepSeek+GLM+Qwen 三模型 consensus
4. **从 Demo 到 SDK**：如何让外部项目一行代码接入 → sdk/ 独立包
5. **从 ChromaDB 到 Milvus**：向量库选型 → Milvus Lite 本地模式 → 多维向量管理后台
