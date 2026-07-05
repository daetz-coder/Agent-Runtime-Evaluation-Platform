# 从零了解本项目 — 完整学习指南

> 48 个核心源文件，12,476 行代码。本文档告诉你**先看什么、后看什么、每份文件解决什么问题**。

---

## 目录

- [一、5 分钟全局认知](#一5-分钟全局认知)
- [二、学习路线图（7 个阶段）](#二学习路线图7-个阶段)
- [三、第 1 阶段：项目入口](#三第-1-阶段项目入口)
- [四、第 2 阶段：SDK 轨迹采集](#四第-2-阶段sdk-轨迹采集)
- [五、第 3 阶段：数据模型与 Schema](#五第-3-阶段数据模型与-schema)
- [六、第 4 阶段：Wiki Agent 业务逻辑](#六第-4-阶段wiki-agent-业务逻辑)
- [七、第 5 阶段：评估引擎](#七第-5-阶段评估引擎)
- [八、第 6 阶段：Sandbox Agent](#八第-6-阶段sandbox-agent)
- [九、第 7 阶段：API 与基础设施](#九第-7-阶段api-与基础设施)
- [十、文件速查表](#十文件速查表)

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

## 二、学习路线图（7 个阶段）

```
第 1 阶段: 项目入口（15 分钟）
  README.md → pyproject.toml → docs/architecture.md

第 2 阶段: SDK 轨迹采集（30 分钟）
  sdk/__init__.py → sdk/collector.py → sdk/schemas.py → sdk/adapters/

第 3 阶段: 数据模型与 Schema（20 分钟）
  app/models/action_types.py → app/models/schemas.py → app/db/models.py

第 4 阶段: Wiki Agent 业务逻辑（45 分钟）
  hooks.py → graph.py → knowledge_agent.py → context_retriever.py → tools/

第 5 阶段: 评估引擎（30 分钟）
  eval_schemas.py → base.py → 6 个评估器 → scoring.py

第 6 阶段: Sandbox Agent（20 分钟）
  runner.py → graph.py → tools/base.py

第 7 阶段: API 与基础设施（15 分钟）
  core/config.py → core/cache.py → services/evaluation_service.py → api/
```

---

## 三、第 1 阶段：项目入口

### `README.md`（241 行）

**读什么**：项目定位、技术栈、目录结构、接入方式

**关键认知**：
- 本项目不是 Prompt Evaluation，是 Agent Runtime Evaluation
- 3 种接入方式：LangGraph Instrument / LLM Proxy / Callback
- 6 维评估体系 + 20 项子指标

### `pyproject.toml`（110 行）

**读什么**：依赖列表，了解技术栈全貌

**关键依赖**：
- FastAPI + Uvicorn（Web 框架）
- LangGraph + LangChain（Agent 编排）
- Milvus Lite（向量数据库）
- Redis（缓存，可选）
- OpenTelemetry（可观测性）

### `docs/architecture.md`

**读什么**：系统架构图、组件关系、数据流

**关键认知**：
- 三大子系统：评估引擎 / Agent Runtime / Wiki Agent
- 双模评测：Sandbox 自动化 / SDK 埋点

---

## 四、第 2 阶段：SDK 轨迹采集

### `sdk/__init__.py`（45 行）

**读什么**：SDK 公开 API 入口

**关键导出**：
- `TrajectoryCollector` — 核心收集器
- `get_collector()` — 获取单例
- `ActionType` — 14 种动作类型
- `instrument_langgraph` — LangGraph 适配器
- `create_proxy_llm` — LLM 代理适配器
- `create_callback_handler` — Callback 适配器

### `sdk/collector.py`（1083 行）⭐⭐⭐

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

### `sdk/schemas.py`（196 行）⭐⭐

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
| ... | ... | ... |

**关键注册表**：`ACTION_DETAIL_SCHEMAS` — action_type → Pydantic 模型映射

### `sdk/adapters/langgraph.py`（428 行）

**读什么**：LangGraph 自动采集适配器

**关键类**：
- `InstrumentedStateGraph` — 包装 StateGraph，自动记录节点执行
- `InstrumentedCompiledGraph` — 包装编译后的图
- `instrument_langgraph(graph)` — 一行接入

**工作原理**：替换 `spec.runnable` 为带采集的 wrapper

### `sdk/adapters/llm_proxy.py`（307 行）

**读什么**：LLM 代理适配器

**关键类**：`ProxyChatModel` — 透明包装 BaseChatModel，自动记录 LLM 调用

### `sdk/adapters/callback.py`（328 行）

**读什么**：LangChain Callback 适配器

**关键类**：`EvalCallbackHandler` — 实现 BaseCallbackHandler，自动采集 LLM/Tool/Chain 事件

---

## 五、第 3 阶段：数据模型与 Schema

### `app/models/action_types.py`（48 行）

**读什么**：从 SDK re-export ActionType + 所有 Pydantic Schema

**关键认知**：这是 app 层使用 SDK Schema 的桥接文件

### `app/models/schemas.py`（394 行）⭐⭐

**读什么**：所有 API 请求/响应的 Pydantic 模型

**关键模型**：

| 模型 | 用途 |
|------|------|
| `TaskCreate` / `TaskResponse` | 任务 CRUD |
| `TrajectoryStep` | 轨迹步骤 |
| `PlanningScore` / `TacticalScore` / ... | 6 维评分 |
| `OverallEvaluation` | 综合评估 |
| `EvaluationResponse` | 评估响应 |
| `JudgeRawData` | Judge 透明面板数据 |

### `app/db/models.py`（118 行）

**读什么**：SQLAlchemy ORM 模型

**3 张核心表**：

| 表 | 字段 | 用途 |
|---|------|------|
| `agent_tasks` | id, goal, context, status | 评估任务 |
| `agent_trajectories` | task_id, step_number, action_type, action_detail(JSON), observation, timestamp | 轨迹步骤 |
| `evaluations` | task_id, 6 维 score, 6 维 feedback(JSON), overall_score | 评估结果 |

---

## 六、第 4 阶段：Wiki Agent 业务逻辑

### `app/wiki_agent/hooks.py`（130 行）⭐

**读什么**：Wiki Agent 与 SDK 的桥梁

**关键函数**：
- `emit_session_start()` → `collector.start_async()`
- `emit_retrieval()` → `collector.record_retrieval()`
- `emit_key_facts()` → `collector.record_memory_write()`
- `emit_response()` → `collector.record(EVIDENCE)`
- `emit_session_end()` → `collector.finish_async()`

**关键认知**：这是"旁路记录"，不影响主流程

### `app/wiki_agent/agent/graph.py`（955 行）⭐⭐⭐

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

### `app/wiki_agent/agent/knowledge_agent.py`（235 行）⭐⭐

**读什么**：知识库维护决策器

**关键类**：`KnowledgeDecision` — Pydantic 模型（action, title, content, path, tags）

**关键函数**：
- `decide_action()` — 优先 with_structured_output，降级 PydanticOutputParser
- `_decide_with_structured_output()` — API 层 schema 约束 + 重试
- `_decide_with_parser()` — 文本解析 + 重试

### `app/wiki_agent/agent/context_retriever.py`（237 行）⭐⭐

**读什么**：四路记忆检索

**四路记忆**：

| 路 | 来源 | 说明 |
|---|------|------|
| Working Memory | chat_history | 最近 10 轮对话 |
| Session Memory | session.key_facts | 会话级事实 |
| User Memory | user_memory.facts | 用户级持久事实 |
| External KB | hybrid_search | 知识库检索 |

**关键函数**：`retrieve_context()` — 合并四路记忆，返回 `RetrievedContext`

### `app/wiki_agent/agent/tools/`（11 个文件）

**读什么**：Wiki Agent 的工具层

| 文件 | 功能 |
|------|------|
| `query_rewriter.py`（487 行） | Query 改写 Pipeline（复杂度分类 + 多策略改写） |
| `vector_store.py`（368 行） | Milvus 向量存储 |
| `sync_manager.py`（346 行） | 四端同步（Markdown + Milvus + BM25 + Git） |
| `bm25_index.py`（285 行） | BM25 关键词索引 |
| `crud_tools.py`（174 行） | 知识条目 CRUD |
| `search_tools.py`（155 行） | 混合搜索（语义 + BM25 + RRF + Rerank） |
| `reranker.py`（157 行） | Cross-Encoder 重排 |
| `env_monitor.py`（214 行） | 文件变化监控 |
| `chunker.py`（83 行） | 文档分块 |
| `embeddings.py`（58 行） | Embedding 模型加载 |

### `app/wiki_agent/config.py`（62 行）

**读什么**：Wiki Agent 配置项

**关键配置**：LLM、Milvus、Embedding、Rerank、Query Rewrite、History

### `app/wiki_agent/bootstrap.py`（190 行）

**读什么**：启动引导流程

**6 步启动**：
1. 创建目录
2. 填充种子知识
3. 初始化 DB
4. 同步索引
5. 预加载模型
6. 启动监控

---

## 七、第 5 阶段：评估引擎

### `app/evaluators/eval_schemas.py`（95 行）⭐⭐

**读什么**：6 个评估器的输出 Pydantic Schema

**关键模型**：

| Schema | 评估器 | 子指标 |
|--------|--------|--------|
| `PlanningEvaluationResult` | PlanningEvaluator | coverage, ordering, granularity, completeness |
| `TacticalEvaluationResult` | TacticalEvaluator | relevance, efficiency, correctness |
| `ToolUseEvaluationResult` | ToolUseEvaluator | selection_quality, parameter_accuracy, result_utilization |
| `MemoryEvaluationResult` | MemoryEvaluator | retention, relevance, consistency |
| `ReplanEvaluationResult` | ReplanEvaluator | trigger_appropriateness, adaptation_quality, learning_from_failure |
| `RetrievalEvaluationResult` | RetrievalEvaluator | relevance, evidence_accuracy, coverage, hallucination_detected |

### `app/evaluators/base.py`（495 行）⭐⭐⭐

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
| `_parse_json_from_llm()` | 鲁棒 JSON 解析（3 种策略） |

### 6 个评估器

| 文件 | 评估维度 | 消费的 ActionType |
|------|---------|------------------|
| `planning_evaluator.py`（217 行） | 规划质量 | PLAN, PLAN_UPDATE |
| `tactical_evaluator.py`（271 行） | 战术决策 | 所有非 PLAN 步骤 |
| `tool_use_evaluator.py`（198 行） | 工具使用 | TOOL_CALL, TOOL_RESULT |
| `memory_evaluator.py`（232 行） | 记忆保持 | MEMORY_WRITE, MEMORY_READ |
| `replan_evaluator.py`（300 行） | 重规划 | REPLAN, FAILURE |
| `retrieval_evaluator.py`（187 行） | 检索质量 | RETRIEVAL, EVIDENCE |

### `app/evaluators/consensus.py`（284 行）

**读什么**：多模型共识评估

**关键类**：`ConsensusEvaluator` — 跨多个 LLM 并行评分，输出均值+标准差

### `app/evaluators/scoring.py`（58 行）

**读什么**：评分工具函数

**关键函数**：`weighted_overall()` — 加权综合分（排除 N/A 维度）

### `app/evaluators/trajectory_compressor.py`（156 行）

**读什么**：轨迹压缩 Pipeline

**4 阶段压缩**：
1. 重要性过滤（按 action_type 权重）
2. THINK 摘要截断（200 字）
3. 滑动窗口（最近 30 步 + 锚点步）
4. 格式化为 LLM 可读文本

---

## 八、第 6 阶段：Sandbox Agent

### `app/agent_runtime/runner.py`（290 行）⭐⭐

**读什么**：Sandbox Agent 的顶层编排器

**关键类**：`AgentRunner` — 协调 Docker 会话、工作区、Agent 图、轨迹采集

**执行流程**：
1. 获取 Docker 会话
2. 设置工作区文件
3. 创建 TrajectoryCollector + ToolProxy
4. 执行 Agent 图
5. 获取轨迹 + flush

### `app/agent_runtime/graph.py`（441 行）⭐⭐

**读什么**：Sandbox Agent 的 LangGraph ReAct 循环

**关键函数**：`create_agent_graph()` — 创建编译后的 StateGraph

**think_and_act 节点**：
- LLM 推理 → 记录 THINK
- 工具调用 → 记录 TOOL_DECISION + TOOL_CALL + TOOL_RESULT + PLAN_UPDATE
- 最终回答 → 记录 EVIDENCE
- 无工具调用 → 记录 REPLAN

### `app/agent_runtime/tools/base.py`（209 行）

**读什么**：工具代理层

**关键类**：`ToolProxy` — 统一工具调用网关（验证、审计、超时、Prometheus 指标、轨迹记录）

---

## 九、第 7 阶段：API 与基础设施

### `app/core/config.py`（154 行）

**读什么**：全局配置

**关键配置项**：服务器、数据库、Redis、LLM Provider、Sandbox、评估权重、可观测性

### `app/core/cache.py`（320 行）

**读什么**：Redis 缓存层（优雅降级）

**关键函数**：`cache_get/set/delete`、`cache_hgetall/hset`、`check_rate_limit`、`hash_prompt`

### `app/services/evaluation_service.py`（1070 行）⭐⭐

**读什么**：评估服务的核心业务逻辑

**关键方法**：
- `create_task()` — 创建评估任务
- `add_trajectory()` — 提交轨迹步骤
- `run_evaluation()` — 运行 6 维评估
- `run_sandbox_evaluation()` — Sandbox 模式评估
- `_persist_evaluation_results()` — 持久化评估结果

### `app/api/v1/endpoints/tasks.py`（208 行）

**读什么**：任务管理 REST API

**关键端点**：
- `POST /tasks/` — 创建任务
- `POST /tasks/{id}/trajectory` — 提交轨迹
- `POST /evaluations/` — 触发评估

---

## 十、文件速查表

### 按优先级排序（⭐ 越多越重要）

| 文件 | 行数 | 功能 | 优先级 |
|------|------|------|--------|
| `sdk/collector.py` | 1083 | SDK 核心：轨迹收集器 | ⭐⭐⭐ |
| `sdk/schemas.py` | 196 | 14 种 ActionType Pydantic Schema | ⭐⭐⭐ |
| `app/wiki_agent/agent/graph.py` | 955 | Wiki Agent 核心编排 | ⭐⭐⭐ |
| `app/evaluators/base.py` | 495 | 评估器基类 | ⭐⭐⭐ |
| `app/evaluators/eval_schemas.py` | 95 | 评估器输出 Schema | ⭐⭐ |
| `app/models/schemas.py` | 394 | API 数据模型 | ⭐⭐ |
| `app/wiki_agent/agent/knowledge_agent.py` | 235 | 知识决策器 | ⭐⭐ |
| `app/wiki_agent/agent/context_retriever.py` | 237 | 四路记忆检索 | ⭐⭐ |
| `app/wiki_agent/hooks.py` | 130 | Wiki Agent SDK 桥梁 | ⭐⭐ |
| `app/agent_runtime/runner.py` | 290 | Sandbox Agent 编排 | ⭐⭐ |
| `app/agent_runtime/graph.py` | 441 | Sandbox Agent 图 | ⭐⭐ |
| `app/services/evaluation_service.py` | 1070 | 评估服务 | ⭐⭐ |
| `app/wiki_agent/agent/tools/query_rewriter.py` | 487 | Query 改写 Pipeline | ⭐⭐ |
| `app/wiki_agent/agent/tools/search_tools.py` | 155 | 混合搜索 | ⭐⭐ |
| `app/wiki_agent/agent/tools/sync_manager.py` | 346 | 四端同步 | ⭐⭐ |
| `app/db/models.py` | 118 | ORM 模型 | ⭐ |
| `app/core/config.py` | 154 | 全局配置 | ⭐ |
| `app/core/cache.py` | 320 | Redis 缓存 | ⭐ |
| `app/wiki_agent/config.py` | 62 | Wiki Agent 配置 | ⭐ |
| `app/wiki_agent/bootstrap.py` | 190 | 启动引导 | ⭐ |

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
