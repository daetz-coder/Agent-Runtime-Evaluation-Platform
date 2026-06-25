# AI Agent 基础设施平台工程师 — 面试准备指南

> 基于岗位 JD 逐项映射，结合 Agent Runtime Evaluation Platform 项目经验

---

## 一、岗位职责与技术映射

### 职责 1：核心模块开发（MCP 中心、Skill 中心、Agent 中心、AI 网关）

| 技术点 | 优先级 | 说明 | 项目对应 |
|--------|--------|------|----------|
| MCP 协议 | 🔴 必须 | Model Context Protocol，标准化 Agent↔工具通信 | ❌ 需新学 |
| A2A 协议 | 🔴 必须 | Agent-to-Agent，Google 提出的多 Agent 协作协议 | ❌ 需新学 |
| Agent 编排 | 🔴 必须 | LangGraph StateGraph、节点编排、状态管理 | ✅ 已用 |
| AI 网关 | 🟡 了解 | LLM 请求路由、限流、模型切换、Token 计量 | ⚠️ 部分（SDK 中间件） |
| API 设计 | 🔴 必须 | RESTful + SSE 流式接口设计 | ✅ 已用 |

### 职责 2：Agent 全生命周期管理（Multi-Agent、沙箱、LLM-as-a-Judge）

| 技术点 | 优先级 | 说明 | 项目对应 |
|--------|--------|------|----------|
| Agent 生命周期 | 🔴 必须 | task 创建→轨迹记录→评估→报告 | ✅ 完整实现 |
| LLM-as-a-Judge | 🔴 必须 | 用 LLM 评估 Agent 输出质量 | ✅ 6 维评估器 |
| Multi-Agent | 🟡 了解 | 多 Agent 协作、任务分解、结果聚合 | ⚠️ SDK 多系统接入 |
| Agent 沙箱 | 🟡 了解 | 隔离执行环境（Docker/gVisor） | ❌ 需新学 |
| Human-in-the-Loop | 🔴 必须 | 人工确认再执行 | ✅ interrupt/resume |

### 职责 3：RAG / LLM 应用开发框架

| 技术点 | 优先级 | 说明 | 项目对应 |
|--------|--------|------|----------|
| 向量检索 | 🔴 必须 | Embedding → ANN 搜索 | ✅ ChromaDB/Milvus |
| BM25 检索 | 🔴 必须 | 关键词检索 + 中文分词 | ✅ rank_bm25 + jieba |
| 混合检索 | 🔴 必须 | 向量 + 关键词融合 | ✅ RRF 倒数秩融合 |
| Reranker | 🔴 必须 | 交叉编码器精排 | ✅ bge-reranker-base ONNX |
| Chunking | 🟡 了解 | 文档分块策略 | ✅ 500 字符 + 50 overlap |
| Advanced RAG | 🟡 了解 | HyDE、Self-RAG、CRAG | ❌ 需新学 |

### 职责 4：基础设施（数据存储、微服务架构）

| 技术点 | 优先级 | 说明 | 项目对应 |
|--------|--------|------|----------|
| SQLite/MySQL | 🔴 必须 | 关系型数据库设计与调优 | ✅ SQLite（可迁移 MySQL） |
| Redis | 🟡 加分 | 缓存、分布式锁、Pub/Sub | ❌ 需新学 |
| 消息队列 | 🟡 加分 | Kafka/RocketMQ 异步处理 | ❌ 需新学 |
| 微服务架构 | 🟡 加分 | 服务拆分、网关、服务治理 | ⚠️ 了解原理 |

---

## 二、必须掌握的核心技术

### 2.1 Agent 工程

#### ReAct 模式
```
Thought → Action → Observation → Thought → ... → Final Answer
```
- Reasoning（推理）和 Acting（行动）交替进行
- 你的项目：search → respond → decide → execute 就是 ReAct 变体

#### Tool Calling
```python
# LLM 决定调用哪个工具、传什么参数
llm.bind_tools([search_tool, create_tool, delete_tool])
response = llm.invoke(messages)  # response.tool_calls
```
- Function Calling（OpenAI）vs Tool Use（Anthropic）
- 你的项目：LangGraph tool 节点 + bind_tools

#### Human-in-the-Loop (HITL)
```python
# LangGraph interrupt/resume 模式
from langgraph.types import interrupt, Command

def execute(state):
    user_confirmed = interrupt({"action": decision})  # 暂停等待
    if user_confirmed:
        # 执行操作
        ...

# 恢复
graph.invoke(Command(resume=True), config)
```
- 你的项目：execute 节点的 interrupt + resume_and_execute

#### MCP 协议（需新学）
```
┌──────────┐     JSON-RPC      ┌──────────────┐
│ MCP Host │ ◄──────────────► │ MCP Server   │
│ (Agent)  │   stdio/SSE/HTTP │ (工具提供方)  │
└──────────┘                   └──────────────┘

核心概念：
- Resources: 数据源（文件、数据库）
- Tools: 可调用函数
- Prompts: 预定义提示模板
- Sampling: LLM 采样请求
```
- 学习资源：https://modelcontextprotocol.io
- 重点：JSON-RPC 2.0、transport 层（stdio vs SSE）、capability negotiation

#### A2A 协议（需新学）
```
┌──────────┐    A2A Protocol    ┌──────────┐
│ Agent A  │ ◄────────────────► │ Agent B  │
│ (Client) │   HTTP + SSE       │ (Server) │
└──────────┘                    └──────────┘

核心概念：
- Agent Card: 能力描述（JSON，类似 OpenAPI）
- Task: 任务生命周期（submitted → working → completed）
- Message/Part: 通信单元
- Streaming: SSE 实时推送
```
- 学习资源：https://google.github.io/A2A

### 2.2 RAG 检索系统

#### 完整检索链路（你的项目已实现）
```
用户查询
    │
    ├── ① Embedding 编码（bge-small-zh, 512 维）
    │       ↓
    │   向量检索（ChromaDB/Milvus, cosine similarity）
    │       ↓
    │   Top-K 候选
    │
    ├── ② BM25 关键词检索（jieba 分词 + Okapi BM25）
    │       ↓
    │   Top-K 候选
    │
    ├── ③ RRF 融合（Reciprocal Rank Fusion）
    │       score = Σ 1/(60 + rank_i)
    │       ↓
    │   合并排序
    │
    └── ④ Reranker 精排（bge-reranker-base, 交叉编码器）
            ↓
        Final Top-K
```

#### 向量数据库对比（面试高频）

| 数据库 | 索引算法 | 特点 | 适用场景 |
|--------|---------|------|----------|
| **Milvus** | HNSW/IVF/DiskANN | 分布式、高性能 | 大规模生产 |
| **ChromaDB** | HNSW | 嵌入式、轻量 | 原型/小规模 |
| **Qdrant** | HNSW | Rust 实现、过滤强 | 中等规模 |
| **Pinecone** | 专有 | 全托管 SaaS | 不想运维 |
| **Weaviate** | HNSW | GraphQL API | 多模态 |
| **FAISS** | IVF/PQ | Meta 开源、纯库 | 研究/嵌入 |

#### Advanced RAG（需补充）

| 技术 | 原理 | 解决的问题 |
|------|------|-----------|
| **HyDE** | 先让 LLM 生成假设答案，用答案做检索 | 查询与文档语义鸿沟 |
| **Self-RAG** | LLM 自评是否需要检索 + 检索结果是否有用 | 不必要的检索、噪声结果 |
| **CRAG** | 检索后先验证文档相关性，不相关则换策略 | 检索质量不稳定 |
| **Query Expansion** | 用 LLM 改写/扩展原始查询 | 查询太窄或模糊 |
| **Parent Document** | 检索到 chunk 后返回父文档 | chunk 上下文不足 |

### 2.3 LLM-as-a-Judge 评测（你的项目核心）

#### 6 维评估体系
```
Trajectory（轨迹）
    │
    ├── PlanningEvaluator (20%)
    │   → 规划质量：目标分解、步骤合理性
    │
    ├── TacticalEvaluator (20%)
    │   → 战术执行：步骤效率、资源利用
    │
    ├── ToolUseEvaluator (15%)
    │   → 工具使用：选择正确性、参数合理性
    │
    ├── MemoryEvaluator (15%)
    │   → 记忆质量：retention × relevance × consistency
    │
    ├── ReplanEvaluator (15%)
    │   → 重规划能力：失败检测、方案调整
    │
    └── RetrievalEvaluator (15%)
        → 检索质量：precision × recall × relevance
```

#### MemoryEvaluator 评分公式
```
overall = retention × 0.45 + relevance × 0.30 + consistency × 0.25

- retention: Agent 是否记住了 key_facts
- relevance: 回忆的信息是否相关
- consistency: 记忆是否自相矛盾
```

#### 评估基准（需了解）

| 基准 | 评估对象 | 说明 |
|------|---------|------|
| **GAIA** | 通用 AI 助手 | 多步推理 + 工具使用 |
| **AgentBench** | Agent 能力 | 8 个环境的综合评测 |
| **SWE-Bench** | 代码 Agent | 真实 GitHub issue 修复 |
| **HumanEval** | 代码生成 | 164 道编程题 |
| **MT-Bench** | 对话质量 | 多轮对话评测 |

---

## 三、系统工程（加分项）

### 3.1 Redis

```
核心用途：
├── 缓存：热点数据缓存，减少 DB 压力
├── 分布式锁：SETNX + 过期时间（或 Redisson）
├── 消息队列：Pub/Sub、Stream（轻量 MQ）
├── 计数器：INCR（限流、Token 计量）
├── 排行榜：ZSET（评估排名）
└── Session 存储：用户会话管理

面试高频题：
- Redis 为什么快？（内存 + 单线程 + IO 多路复用）
- 缓存穿透/击穿/雪崩？
- 分布式锁实现（SETNX vs Redlock）
- Redis 持久化（RDB vs AOF）
```

### 3.2 消息队列

```
Kafka vs RocketMQ vs RabbitMQ：

| 特性     | Kafka        | RocketMQ     | RabbitMQ     |
|---------|-------------|-------------|-------------|
| 吞吐量   | 极高(百万/s) | 高(十万/s)   | 中(万/s)     |
| 延迟     | ms 级        | ms 级        | μs 级        |
| 可靠性   | 副本机制      | 事务消息      | 确认机制      |
| 适用场景 | 日志/大数据   | 金融/电商     | 实时通信      |

面试高频题：
- 如何保证消息不丢失？（生产确认 + 持久化 + 消费确认）
- 如何保证顺序消费？（分区有序 + 单消费者）
- Exactly-Once 语义如何实现？
```

### 3.3 MySQL 调优

```
面试高频题：
- EXPLAIN 各字段含义？（type, key, rows, Extra）
- 索引设计原则？（最左前缀、覆盖索引、索引下推）
- 慢查询排查步骤？（slow_log → EXPLAIN → 优化索引/SQL）
- 分库分表方案？（ShardingSphere、垂直拆分 vs 水平拆分）
- 事务隔离级别？（RR 下的 MVCC 实现、Gap Lock）
```

### 3.4 分布式系统

```
核心概念：
- CAP 定理：一致性 vs 可用性 vs 分区容错
- 分布式事务：2PC、TCC、Saga 模式
- 一致性协议：Raft、Paxos
- 服务治理：注册发现、负载均衡、熔断降级

你的项目可以讲：
- SDK 的离线模式（CAP 中的 AP 选择）
- 指数退避重试（分布式系统常见模式）
- 单例 + 线程安全（并发控制）
```

---

## 四、项目包装（STAR 方法）

### 项目：Agent Runtime Evaluation Platform

#### Situation（背景）
> 企业级 AI Agent 需要标准化的评估体系来衡量规划、工具使用、记忆、检索等能力，
> 但现有方案要么侵入性强（需要改 Agent 代码），要么评估维度单一。

#### Task（任务）
> 设计并实现一个零侵入的 Agent 运行时评估平台，支持 6 维自动评估、
> 多系统接入、轨迹可视化。

#### Action（行动）
> 1. **SDK 设计**：3 种接入模式（LangGraph 包裹 / LLM Proxy / Callback），
>    一行代码接入，自动采集 14 种 action type
> 2. **6 维评估器**：Planning / Tactical / ToolUse / Memory / Replan / Retrieval，
>    每个维度用 LLM-as-a-Judge + 加权评分
> 3. **混合检索**：语义向量 + BM25 + RRF 融合 + Reranker 精排，完整 RAG pipeline
> 4. **Trajectory 压缩**：4 阶段管线（重要性过滤→思考摘要→滑动窗口→上下文构建），
>    减少 LLM Judge 的 token 消耗
> 5. **Session 记忆**：key_facts 长期记忆 + LLM 自动提取 + task 连续性判断
> 6. **解耦架构**：评估平台与 Agent 完全分离，单源真相，多系统共享

#### Result（结果）
> - SDK 支持 Python / 非 Python 系统接入
> - 6 维评估覆盖 Agent 全能力维度
> - Trajectory 压缩减少 ~60% token 消耗
> - 系统检查器可视化 checkpoint / session / BM25 内部状态

---

## 五、学习路线（4 周计划）

### 第 1 周：MCP + A2A 协议

```
Day 1-2: MCP 协议
  □ 读 MCP 规范 (modelcontextprotocol.io)
  □ 用 Python 实现一个 mcp-server (filesystem search)
  □ 用 mcp-client 连接并调用

Day 3-4: A2A 协议
  □ 读 A2A 规范 (google.github.io/A2A)
  □ 理解 Agent Card / Task / Message 模型
  □ 实现两个 Agent 间的简单任务委托

Day 5: 对比总结
  □ MCP vs A2A 的定位差异
  □ 与 OpenAI Function Calling 的关系
```

### 第 2 周：分布式系统补课

```
Day 1-2: Redis
  □ Docker 启动 Redis
  □ 实现：缓存 + 分布式锁 + Pub/Sub
  □ 刷题：Redis 面试 20 题

Day 3-4: 消息队列
  □ Kafka 基础：Topic / Partition / Consumer Group
  □ 实现：异步评估任务队列
  □ 刷题：MQ 面试 15 题

Day 5: MySQL
  □ EXPLAIN 实战
  □ 索引优化案例
  □ 分库分表方案设计
```

### 第 3 周：RAG 进阶 + Fine-tuning

```
Day 1-2: Advanced RAG
  □ 实现 HyDE（假设文档嵌入）
  □ 了解 Self-RAG / CRAG 论文
  □ 向量数据库对比（HNSW vs IVF vs PQ）

Day 3-4: Fine-tuning
  □ LoRA 原理 + 实践（用 PEFT 微调一个小模型）
  □ SFT 数据准备格式
  □ 了解 RLHF / DPO

Day 5: Prompt Engineering
  □ CoT / Few-shot / Self-Consistency
  □ 评估 Prompt 设计技巧
  □ Prompt 注入防御
```

### 第 4 周：系统设计 + 面试准备

```
Day 1-2: 系统设计题
  □ "设计一个 MCP 中心"（服务注册 + 发现 + 代理）
  □ "设计 Multi-Agent 协作平台"（任务分解 + 调度 + 聚合）
  □ "设计 Agent 运行沙箱"（隔离 + 资源限制 + 安全）

Day 3-4: 项目包装
  □ 用 STAR 方法准备 3 个项目故事
  □ 准备技术深度追问（为什么选 RRF？为什么用 ONNX？）
  □ 准备"你做过最难的技术决策"

Day 5: 算法
  □ LeetCode 中等 30 题（重点：树、图、动态规划）
  □ 手写：LRU Cache、线程安全单例、RRF 融合
```

---

## 六、面试高频问题速查

### Agent 工程

| 问题 | 要点 |
|------|------|
| ReAct 和 Plan-and-Execute 区别？ | ReAct 交替推理行动；P&E 先规划再执行 |
| Tool Calling 底层原理？ | LLM 输出结构化 JSON，框架解析后调用函数 |
| MCP 解决了什么问题？ | 标准化工具接入协议，避免每个 Agent 自己造轮子 |
| Agent 幻觉怎么处理？ | RAG grounding + 事实核查 + HITL 确认 |
| 如何评估 Agent 质量？ | 多维度 LLM-as-a-Judge + 人工抽检 |

### RAG

| 问题 | 要点 |
|------|------|
| 向量检索和关键词检索优劣？ | 向量：语义理解强，精确匹配弱；BM25 反之 |
| RRF 原理？ | score = Σ 1/(k + rank)，融合多路排序 |
| Chunk 大小怎么选？ | 500-1000 字符，overlap 10-20%，按段落边界切 |
| Embedding 模型怎么选？ | MTEB 排行榜，中文选 bge 系列 |
| 检索结果不相关怎么办？ | Reranker + HyDE + Query Expansion |

### 系统设计

| 问题 | 要点 |
|------|------|
| 如何设计零侵入 SDK？ | 代理模式 + 自动埋点 + 环境变量配置 |
| 如何处理长轨迹？ | 压缩管线：过滤→摘要→窗口→构建 |
| 如何保证数据不丢失？ | 批量缓冲 + 失败回退 + 指数退避重试 |
| 多系统如何共享代码？ | 单源真相 + 薄代理层 |

---

## 七、推荐学习资源

| 资源 | 链接 | 说明 |
|------|------|------|
| MCP 官方文档 | modelcontextprotocol.io | 协议规范 + SDK |
| A2A 官方文档 | google.github.io/A2A | 协议规范 |
| LangGraph 文档 | langchain-ai.github.io/langgraph | 状态图编排 |
| LangChain 文档 | python.langchain.com | LLM 应用框架 |
| Milvus 文档 | milvus.io/docs | 向量数据库 |
| RAG 综述论文 | arxiv.org/abs/2312.10997 | Retrieval-Augmented Generation 全面综述 |
| LLM-as-a-Judge | arxiv.org/abs/2306.05685 | Judging LLM-as-a-Judge 论文 |
| GAIA Benchmark | gaia-benchmark.github.io | 通用 AI 助手评测 |
| Redis 官方教程 | redis.io/docs | 缓存 + 分布式 |
| 系统设计入门 | github.com/donnemartin/system-design-primer | 经典系统设计 |
