# 从零了解本项目 — 完整学习指南

> 本文档覆盖**文档层 + 源码层**的完整学习路径。按顺序阅读，从架构认知到代码细节。

---

## 目录

- [一、5 分钟全局认知](#一5-分钟全局认知)
- [二、完整学习路线（4 个层次）](#二完整学习路线4-个层次)
- [三、第 1 层：文档层 — 理解"做什么"](#三第-1-层文档层--理解做什么)
- [四、第 2 层：SDK 层 — 理解"怎么采集"](#四第-2-层sdk-层--理解怎么采集)
- [五、第 3 层：业务层 — 理解"怎么运行"](#五第-3-层业务层--理解怎么运行)
- [六、第 4 层：评估层 — 理解"怎么评分"](#六第-4-层评估层--理解怎么评分)
- [七、文件速查表](#七文件速查表)

---

## 一、5 分钟全局认知

```
本项目 = AI Agent 运行时质量评估平台

两条流：
  流 1: Agent 执行 → 产生轨迹 → 存入 DB
  流 2: 评估引擎 → 读取轨迹 → LLM 评分 → 存入 DB

两种 Agent：
  Wiki Agent   — RAG 知识库问答（嵌入平台进程）
  Sandbox Agent — Docker 沙箱执行（平台控制运行）

6 个评估维度：
  Planning / Tactical / Tool Use / Memory / Replan / Retrieval
```

**一句话**：Agent 做业务，顺便记录轨迹；评估平台读轨迹，独立做评分。

---

## 二、完整学习路线（4 个层次）

```
第 1 层: 文档层（理解"做什么"）           预计 60 分钟
  ├── 项目文档（README、架构、设计）
  ├── Wiki Agent 文档（概述、难点、记忆）
  └── 数据流文档（采集架构、双流架构）

第 2 层: SDK 层（理解"怎么采集"）          预计 45 分钟
  ├── SDK 入口（__init__.py）
  ├── 核心收集器（collector.py）
  ├── Pydantic Schema（schemas.py）
  └── 适配器（langgraph.py、llm_proxy.py、callback.py）

第 3 层: 业务层（理解"怎么运行"）          预计 60 分钟
  ├── 数据模型（action_types.py、schemas.py、db/models.py）
  ├── 配置（config.py、cache.py）
  ├── Wiki Agent（hooks.py → graph.py → knowledge_agent.py → tools/）
  └── Sandbox Agent（runner.py → graph.py → tools/base.py）

第 4 层: 评估层（理解"怎么评分"）          预计 45 分钟
  ├── 评估器 Schema（eval_schemas.py）
  ├── 评估器基类（base.py）
  ├── 6 个评估器
  └── 评分工具（scoring.py、consensus.py、compressor.py）
```

---

## 三、第 1 层：文档层 — 理解"做什么"

### 阅读顺序

```
① README.md                          ← 入口，5 分钟
② docs/architecture.md               ← 架构图，10 分钟
③ docs/two-flow-architecture.md      ← 双流架构，10 分钟
④ docs/data-collection-architecture.md ← 数据采集，10 分钟
⑤ docs/wiki-agent-overview.md        ← Wiki Agent，15 分钟
⑥ docs/wiki-agent-memory-architecture.md ← 记忆体系，10 分钟
```

### ① `README.md`（241 行）

**读什么**：项目定位、技术栈、目录结构、接入方式

**关键认知**：
- 本项目不是 Prompt Evaluation，是 Agent Runtime Evaluation
- 3 种接入方式：LangGraph Instrument / LLM Proxy / Callback
- 6 维评估体系 + 20 项子指标

### ② `docs/architecture.md`

**读什么**：系统架构图、组件关系、数据流

**关键认知**：
- 三大子系统：评估引擎 / Agent Runtime / Wiki Agent
- 双模评测：Sandbox 自动化 / SDK 埋点

### ③ `docs/two-flow-architecture.md`

**读什么**：Wiki Agent 流 + 评估平台流的完整对比

**关键认知**：
- Wiki Agent 做业务，顺便记录轨迹
- 评估平台读轨迹，独立做评分
- 两条流通过 DB 解耦

### ④ `docs/data-collection-architecture.md`

**读什么**：数据采集的四条路径（现合并为两条）、14 种 ActionType、数据库表结构

**关键认知**：
- SDK HTTP 模式 + Sandbox 模式
- 14 种 ActionType 的数据格式
- agent_trajectories 表结构

### ⑤ `docs/wiki-agent-overview.md`

**读什么**：Wiki Agent 的完整架构、目录结构、所有组件功能

**关键认知**：
- LangGraph 四节点：search → respond → decide → execute
- 四端同步：Markdown + Milvus + BM25 + Git
- 混合检索：语义 + BM25 + RRF + Rerank

### ⑥ `docs/wiki-agent-memory-architecture.md`

**读什么**：四路记忆 + 六层压缩

**关键认知**：
- Working Memory / Session Memory / User Memory / External KB
- 六层压缩：SQL 截断 → 滑动窗口 → 二次保护 → 字符预算 → LLM 提炼 → 分块截断

### 可选文档

| 文档 | 内容 | 何时读 |
|------|------|--------|
| `docs/wiki-agent-difficult-points.md` | 10 个技术难点 | 深入理解时 |
| `docs/wiki-agent-learning-guide.md` | Wiki Agent 学习路径 | 专门学 Wiki Agent 时 |
| `docs/wiki-agent-optimization-report.md` | 性能优化（55s→3s） | 关注性能时 |
| `docs/tech-stack-rationale.md` | 技术选型理由 | 做技术决策时 |
| `docs/design.md` | 设计思路 | 理解设计哲学时 |

---

## 四、第 2 层：SDK 层 — 理解"怎么采集"

### 阅读顺序

```
① sdk/__init__.py                    ← SDK 入口，2 分钟
② sdk/schemas.py                     ← 14 种 Schema，10 分钟
③ sdk/collector.py                   ← 核心收集器，20 分钟
④ sdk/adapters/langgraph.py          ← LangGraph 适配器，10 分钟
⑤ sdk/adapters/llm_proxy.py          ← LLM 代理适配器，5 分钟
⑥ sdk/adapters/callback.py           ← Callback 适配器，5 分钟
```

### ① `sdk/__init__.py`（45 行）

**读什么**：SDK 公开 API 入口

**关键导出**：
- `TrajectoryCollector` — 核心收集器
- `get_collector()` — 获取单例
- `ActionType` — 14 种动作类型
- `instrument_langgraph` — LangGraph 适配器
- `create_proxy_llm` — LLM 代理适配器
- `create_callback_handler` — Callback 适配器

### ② `sdk/schemas.py`（196 行）⭐⭐

**读什么**：14 种 ActionType 的 Pydantic Schema 定义

**关键模型**：

| Schema | 对应 ActionType | 必填字段 |
|--------|----------------|---------|
| `PlanDetail` | PLAN | goal |
| `ToolCallDetail` | TOOL_CALL | tool_name |
| `RetrievalDetail` | RETRIEVAL | query |
| `MemoryWriteDetail` | MEMORY_WRITE | key, value |
| `FailureDetail` | FAILURE | error_type, error_message |
| `EvidenceDetail` | EVIDENCE | evidence_type |

**关键注册表**：`ACTION_DETAIL_SCHEMAS` — action_type → Pydantic 模型映射

### ③ `sdk/collector.py`（1083 行）⭐⭐⭐

**读什么**：SDK 核心，所有轨迹采集的底层实现

**关键类/函数**：

| 组件 | 作用 |
|------|------|
| `ActionType` | 14 种动作类型常量 |
| `TrajectoryCollector` | 单例收集器，缓冲+批量上传 |
| `record()` | 核心记录方法，Pydantic 校验+截断 |
| `start()` / `finish()` | 任务生命周期 |
| `start_async()` / `finish_async()` | 异步版本，`asyncio.to_thread` 避免自死锁 |
| `record_*()` | 14 个便捷方法 |
| `get_collector()` | 获取全局单例 |

**关键设计**：
- `ContextVar` 实现并发请求隔离
- `_short()` 截断过长数据（4000 字符）
- `_validate_step()` Pydantic Schema 校验
- 批量 flush + 失败回退缓冲

### ④ `sdk/adapters/langgraph.py`（428 行）

**读什么**：LangGraph 自动采集适配器

**关键类**：
- `InstrumentedStateGraph` — 包装 StateGraph，自动记录节点执行
- `instrument_langgraph(graph)` — 一行接入

**工作原理**：替换 `spec.runnable` 为带采集的 wrapper

### ⑤ `sdk/adapters/llm_proxy.py`（307 行）

**读什么**：LLM 代理适配器

**关键类**：`ProxyChatModel` — 透明包装 BaseChatModel，自动记录 LLM 调用

### ⑥ `sdk/adapters/callback.py`（328 行）

**读什么**：LangChain Callback 适配器

**关键类**：`EvalCallbackHandler` — 实现 BaseCallbackHandler，自动采集 LLM/Tool/Chain 事件

---

## 五、第 3 层：业务层 — 理解"怎么运行"

### 阅读顺序

```
① app/models/action_types.py        ← Schema re-export，2 分钟
② app/db/models.py                   ← ORM 模型，5 分钟
③ app/models/schemas.py              ← API 数据模型，10 分钟
④ app/core/config.py                 ← 全局配置，5 分钟
⑤ app/core/cache.py                  ← Redis 缓存，5 分钟
⑥ app/wiki_agent/config.py           ← Wiki Agent 配置，3 分钟
⑦ app/wiki_agent/bootstrap.py        ← 启动引导，5 分钟
⑧ app/wiki_agent/hooks.py            ← SDK 桥梁，5 分钟
⑨ app/wiki_agent/agent/graph.py      ← Wiki Agent 核心，30 分钟
⑩ app/wiki_agent/agent/knowledge_agent.py ← 知识决策，10 分钟
⑪ app/wiki_agent/agent/context_retriever.py ← 四路记忆，10 分钟
⑫ app/wiki_agent/agent/tools/*.py    ← 工具层，20 分钟
⑬ app/agent_runtime/runner.py        ← Sandbox 编排，10 分钟
⑭ app/agent_runtime/graph.py         ← Sandbox 图，15 分钟
⑮ app/agent_runtime/tools/base.py    ← 工具代理，5 分钟
```

### ① `app/models/action_types.py`（48 行）

**读什么**：从 SDK re-export ActionType + 所有 Pydantic Schema

### ② `app/db/models.py`（118 行）

**读什么**：SQLAlchemy ORM 模型

**3 张核心表**：

| 表 | 字段 | 用途 |
|---|------|------|
| `agent_tasks` | id, goal, context, status | 评估任务 |
| `agent_trajectories` | task_id, step_number, action_type, action_detail(JSON), observation, timestamp | 轨迹步骤 |
| `evaluations` | task_id, 6 维 score, 6 维 feedback(JSON), overall_score | 评估结果 |

### ③ `app/models/schemas.py`（394 行）⭐⭐

**读什么**：所有 API 请求/响应的 Pydantic 模型

**关键模型**：
- `TaskCreate` / `TaskResponse` — 任务 CRUD
- `TrajectoryStep` — 轨迹步骤
- `PlanningScore` / `TacticalScore` / ... — 6 维评分
- `EvaluationResponse` — 评估响应

### ④ `app/core/config.py`（154 行）

**读什么**：全局配置

**关键配置项**：服务器、数据库、Redis、LLM Provider、Sandbox、评估权重、可观测性

### ⑤ `app/core/cache.py`（320 行）

**读什么**：Redis 缓存层（优雅降级）

**关键函数**：`cache_get/set/delete`、`check_rate_limit`、`hash_prompt`

### ⑥ `app/wiki_agent/config.py`（62 行）

**读什么**：Wiki Agent 配置项

**关键配置**：LLM、Milvus、Embedding、Rerank、Query Rewrite、History

### ⑦ `app/wiki_agent/bootstrap.py`（190 行）

**读什么**：启动引导流程

**6 步启动**：创建目录 → 填充种子知识 → 初始化 DB → 同步索引 → 预加载模型 → 启动监控

### ⑧ `app/wiki_agent/hooks.py`（130 行）⭐

**读什么**：Wiki Agent 与 SDK 的桥梁

**关键函数**：
- `emit_session_start()` → `collector.start_async()`
- `emit_retrieval()` → `collector.record_retrieval()`
- `emit_key_facts()` → `collector.record_memory_write()`
- `emit_response()` → `collector.record(EVIDENCE)`
- `emit_session_end()` → `collector.finish_async()`

### ⑨ `app/wiki_agent/agent/graph.py`（955 行）⭐⭐⭐

**读什么**：Wiki Agent 核心编排，LangGraph 四节点工作流

**四个节点**：

```
search → respond → decide → execute
  │         │         │        │
  │         │         │        └─ HITL 中断 + CRUD 执行
  │         │         └─ with_structured_output(KnowledgeDecision)
  │         └─ LLM 流式生成回复
  └─ 检索四路记忆 + 记录 PLAN_UPDATE
```

**关键函数**：
- `search()` — 检索 + 记录 RETRIEVAL/MEMORY_READ/EVIDENCE/PLAN_UPDATE
- `respond()` — LLM 生成回复 + 记录 THINK
- `decide()` — 知识决策 + 记录 TOOL_DECISION/PLAN_UPDATE
- `execute()` — HITL + CRUD + 记录 TOOL_CALL/REPLAN
- `run_chat_stream()` — SSE 流式入口
- `resume_and_execute()` — HITL 恢复

### ⑩ `app/wiki_agent/agent/knowledge_agent.py`（235 行）⭐⭐

**读什么**：知识库维护决策器

**关键类**：`KnowledgeDecision` — Pydantic 模型（action, title, content, path, tags）

**关键函数**：
- `decide_action()` — 优先 with_structured_output，降级 PydanticOutputParser
- `_decide_with_structured_output()` — API 层 schema 约束 + 重试
- `_decide_with_parser()` — 文本解析 + 重试

### ⑪ `app/wiki_agent/agent/context_retriever.py`（237 行）⭐⭐

**读什么**：四路记忆检索

**四路记忆**：

| 路 | 来源 | 说明 |
|---|------|------|
| Working Memory | chat_history | 最近 10 轮对话 |
| Session Memory | session.key_facts | 会话级事实 |
| User Memory | user_memory.facts | 用户级持久事实 |
| External KB | hybrid_search | 知识库检索 |

### ⑫ `app/wiki_agent/agent/tools/`（10 个文件）

**阅读顺序**：

```
search_tools.py    ← 混合搜索入口（最先读）
query_rewriter.py  ← Query 改写 Pipeline
vector_store.py    ← Milvus 向量存储
bm25_index.py      ← BM25 关键词索引
reranker.py        ← Cross-Encoder 重排
chunker.py         ← 文档分块
embeddings.py      ← Embedding 模型
crud_tools.py      ← 知识条目 CRUD
sync_manager.py    ← 四端同步
env_monitor.py     ← 文件变化监控
```

### ⑬ `app/agent_runtime/runner.py`（290 行）⭐⭐

**读什么**：Sandbox Agent 的顶层编排器

**执行流程**：获取 Docker 会话 → 设置工作区 → 创建 Collector + ToolProxy → 执行 Agent 图 → 获取轨迹

### ⑭ `app/agent_runtime/graph.py`（441 行）⭐⭐

**读什么**：Sandbox Agent 的 LangGraph ReAct 循环

**think_and_act 节点**：
- LLM 推理 → 记录 THINK
- 工具调用 → 记录 TOOL_DECISION + TOOL_CALL + TOOL_RESULT + PLAN_UPDATE
- 最终回答 → 记录 EVIDENCE
- 无工具调用 → 记录 REPLAN

### ⑮ `app/agent_runtime/tools/base.py`（209 行）

**读什么**：工具代理层

**关键类**：`ToolProxy` — 统一工具调用网关（验证、审计、超时、轨迹记录）

---

## 六、第 4 层：评估层 — 理解"怎么评分"

### 阅读顺序

```
① app/evaluators/eval_schemas.py     ← 输出 Schema，5 分钟
② app/evaluators/base.py             ← 评估器基类，15 分钟
③ app/evaluators/planning_evaluator.py ← 规划评估，10 分钟
④ app/evaluators/tool_use_evaluator.py ← 工具评估，10 分钟
⑤ app/evaluators/retrieval_evaluator.py ← 检索评估，10 分钟
⑥ app/evaluators/tactical_evaluator.py ← 战术评估，5 分钟
⑦ app/evaluators/memory_evaluator.py  ← 记忆评估，5 分钟
⑧ app/evaluators/replan_evaluator.py  ← 重规划评估，5 分钟
⑨ app/evaluators/consensus.py         ← 多模型共识，5 分钟
⑩ app/evaluators/scoring.py           ← 评分工具，3 分钟
⑪ app/evaluators/trajectory_compressor.py ← 轨迹压缩，5 分钟
⑫ app/services/evaluation_service.py  ← 评估服务，15 分钟
```

### ① `app/evaluators/eval_schemas.py`（95 行）⭐⭐

**读什么**：6 个评估器的输出 Pydantic Schema

| Schema | 评估器 | 子指标 |
|--------|--------|--------|
| `PlanningEvaluationResult` | PlanningEvaluator | coverage, ordering, granularity, completeness |
| `TacticalEvaluationResult` | TacticalEvaluator | relevance, efficiency, correctness |
| `ToolUseEvaluationResult` | ToolUseEvaluator | selection_quality, parameter_accuracy, result_utilization |
| `MemoryEvaluationResult` | MemoryEvaluator | retention, relevance, consistency |
| `ReplanEvaluationResult` | ReplanEvaluator | trigger_appropriateness, adaptation_quality, learning_from_failure |
| `RetrievalEvaluationResult` | RetrievalEvaluator | relevance, evidence_accuracy, coverage, hallucination_detected |

### ② `app/evaluators/base.py`（495 行）⭐⭐⭐

**读什么**：评估器基类，所有评估器的公共逻辑

**关键方法**：

| 方法 | 作用 |
|------|------|
| `_format_trajectory()` | 轨迹格式化（4 阶段压缩） |
| `_extract_plans()` | 提取 PLAN 步骤 |
| `_extract_tool_calls()` | 提取 TOOL_CALL 步骤 |
| `_extract_memory_events()` | 提取 MEMORY_WRITE/READ 步骤 |
| `_invoke_structured_llm()` | with_structured_output + 重试 |
| `_invoke_llm_cached()` | Redis 缓存的 LLM 调用 |

### ③-⑧ 6 个评估器

| 文件 | 评估维度 | 消费的 ActionType |
|------|---------|------------------|
| `planning_evaluator.py` | 规划质量 | PLAN, PLAN_UPDATE |
| `tactical_evaluator.py` | 战术决策 | 所有非 PLAN 步骤 |
| `tool_use_evaluator.py` | 工具使用 | TOOL_CALL, TOOL_RESULT |
| `memory_evaluator.py` | 记忆保持 | MEMORY_WRITE, MEMORY_READ |
| `replan_evaluator.py` | 重规划 | REPLAN, FAILURE |
| `retrieval_evaluator.py` | 检索质量 | RETRIEVAL, EVIDENCE |

### ⑨ `app/evaluators/consensus.py`（284 行）

**读什么**：多模型共识评估

**关键类**：`ConsensusEvaluator` — 跨多个 LLM 并行评分，输出均值+标准差

### ⑩ `app/evaluators/scoring.py`（58 行）

**读什么**：评分工具函数

**关键函数**：`weighted_overall()` — 加权综合分（排除 N/A 维度）

### ⑪ `app/evaluators/trajectory_compressor.py`（156 行）

**读什么**：轨迹压缩 Pipeline

**4 阶段压缩**：重要性过滤 → THINK 摘要截断 → 滑动窗口 → 格式化

### ⑫ `app/services/evaluation_service.py`（1070 行）⭐⭐

**读什么**：评估服务的核心业务逻辑

**关键方法**：
- `create_task()` — 创建评估任务
- `add_trajectory()` — 提交轨迹步骤
- `run_evaluation()` — 运行 6 维评估
- `run_sandbox_evaluation()` — Sandbox 模式评估
- `_persist_evaluation_results()` — 持久化评估结果

---

## 七、文件速查表

### 按阅读优先级排序

| 优先级 | 文件 | 行数 | 功能 |
|--------|------|------|------|
| ⭐⭐⭐ | `sdk/collector.py` | 1083 | SDK 核心：轨迹收集器 |
| ⭐⭐⭐ | `sdk/schemas.py` | 196 | 14 种 ActionType Pydantic Schema |
| ⭐⭐⭐ | `app/wiki_agent/agent/graph.py` | 955 | Wiki Agent 核心编排 |
| ⭐⭐⭐ | `app/evaluators/base.py` | 495 | 评估器基类 |
| ⭐⭐ | `app/evaluators/eval_schemas.py` | 95 | 评估器输出 Schema |
| ⭐⭐ | `app/models/schemas.py` | 394 | API 数据模型 |
| ⭐⭐ | `app/wiki_agent/agent/knowledge_agent.py` | 235 | 知识决策器 |
| ⭐⭐ | `app/wiki_agent/agent/context_retriever.py` | 237 | 四路记忆检索 |
| ⭐⭐ | `app/wiki_agent/hooks.py` | 130 | Wiki Agent SDK 桥梁 |
| ⭐⭐ | `app/agent_runtime/runner.py` | 290 | Sandbox Agent 编排 |
| ⭐⭐ | `app/agent_runtime/graph.py` | 441 | Sandbox Agent 图 |
| ⭐⭐ | `app/services/evaluation_service.py` | 1070 | 评估服务 |
| ⭐⭐ | `app/wiki_agent/agent/tools/query_rewriter.py` | 487 | Query 改写 Pipeline |
| ⭐⭐ | `app/wiki_agent/agent/tools/search_tools.py` | 155 | 混合搜索 |
| ⭐⭐ | `app/wiki_agent/agent/tools/sync_manager.py` | 346 | 四端同步 |
| ⭐ | `app/db/models.py` | 118 | ORM 模型 |
| ⭐ | `app/core/config.py` | 154 | 全局配置 |
| ⭐ | `app/core/cache.py` | 320 | Redis 缓存 |
| ⭐ | `app/wiki_agent/config.py` | 62 | Wiki Agent 配置 |
| ⭐ | `app/wiki_agent/bootstrap.py` | 190 | 启动引导 |

### 按功能模块分组

```
SDK 层（数据采集）:
  sdk/collector.py          — 核心收集器
  sdk/schemas.py            — 14 种 Schema
  sdk/adapters/langgraph.py — LangGraph 适配器
  sdk/adapters/llm_proxy.py — LLM 代理适配器
  sdk/adapters/callback.py  — Callback 适配器

Wiki Agent（业务逻辑）:
  app/wiki_agent/agent/graph.py            — 核心编排
  app/wiki_agent/agent/knowledge_agent.py  — 知识决策
  app/wiki_agent/agent/context_retriever.py — 四路记忆
  app/wiki_agent/hooks.py                  — SDK 桥梁
  app/wiki_agent/agent/tools/              — 工具层（10 个文件）

评估引擎（评分）:
  app/evaluators/base.py       — 基类
  app/evaluators/eval_schemas.py — 输出 Schema
  app/evaluators/planning_evaluator.py    — 规划评估
  app/evaluators/tactical_evaluator.py    — 战术评估
  app/evaluators/tool_use_evaluator.py    — 工具评估
  app/evaluators/memory_evaluator.py      — 记忆评估
  app/evaluators/replan_evaluator.py      — 重规划评估
  app/evaluators/retrieval_evaluator.py   — 检索评估
  app/evaluators/consensus.py             — 多模型共识
  app/evaluators/scoring.py               — 评分工具

Sandbox Agent（沙箱执行）:
  app/agent_runtime/runner.py    — 编排器
  app/agent_runtime/graph.py     — Agent 图
  app/agent_runtime/tools/base.py — 工具代理

基础设施:
  app/core/config.py              — 全局配置
  app/core/cache.py               — Redis 缓存
  app/db/models.py                — ORM 模型
  app/models/schemas.py           — API 模型
  app/models/action_types.py      — Schema re-export
  app/services/evaluation_service.py — 评估服务
```

### 统计

| 类别 | 文件数 | 总行数 |
|------|--------|--------|
| 文档层 | 6 个核心文档 | — |
| SDK 层 | 7 个源文件 | 2,414 |
| 业务层 | 20 个源文件 | 5,231 |
| 评估层 | 12 个源文件 | 2,296 |
| 基础设施 | 6 个源文件 | 1,162 |
| **总计** | **51 个源文件** | **~12,500** |
