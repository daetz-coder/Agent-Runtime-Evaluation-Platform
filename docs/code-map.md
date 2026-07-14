# 项目核心代码导读

> 时间有限时，按优先级阅读这两个 Agent 的核心代码。
> 每个 Agent 只需读 3 个文件即可覆盖完整链路。

---

## 一、Wiki-Agent（被评估的对象）

用户提问 → 检索知识库 → LLM 生成回答 → 决定是否 CRUD → 返回

### 必读（⭐⭐⭐）

| 文件 | 行数 | 核心职责 |
|---|---|---|
| `app/wiki_agent/agent/graph.py` | 1079 | LangGraph 图定义 + 4 个节点 + 运行入口 |
| `app/wiki_agent/agent/context_retriever.py` | 237 | 四路记忆统一检索 |
| `app/wiki_agent/routers/chat.py` | 266 | FastAPI 路由 + SSE 流式输出 |

### 建议读（⭐⭐）

| 文件 | 行数 | 核心职责 |
|---|---|---|
| `app/wiki_agent/agent/tools/query_rewriter.py` | 513 | Query 复杂度分级 + 改写 |
| `app/wiki_agent/agent/knowledge_agent.py` | 375 | LLM 决定 CRUD 操作 |
| `app/wiki_agent/session/store.py` | 457 | 用户级/会话级记忆 |
| `app/wiki_agent/agent/tools/search_tools.py` | -- | Milvus + BM25 + RRF + Rerank |

### 阅读路径

```
chat.py:71  stream_response()
  → 入口：接收用户消息，构建 history
  → 调用 run_chat_stream()

graph.py  run_chat_stream()
  → await start() 创建评估任务（pending）
  → graph.ainvoke() 进入 LangGraph
  → await finish(auto_run=False) 仅 flush 轨迹，保持 pending

graph.py:391  search()
  → _generate_plan() 生成计划
  → retrieve_context() 四路检索

context_retriever.py:51  retrieve_context()
  → rewrite_query() 改写
  → hybrid_search() 混合检索
  → get_user_memory() / get_session_key_facts()

graph.py:588  respond()
  → _build_llm_messages() 构建 prompt
  → chat_llm.astream() LLM 流式输出

graph.py:637  decide()
  → knowledge_agent.decide_action() 决定 CRUD

graph.py:672  execute()
  → interrupt() HITL 等待确认
  → crud_tools.* CRUD 执行
```

---

## 二、评估平台（评估者）

轨迹数据 → 6 维评估器并行 → 加权聚合 → 结果入库

### 必读（⭐⭐⭐）

| 文件 | 行数 | 核心职责 |
|---|---|---|
| `app/services/evaluation_service.py` | 893 | 评估全流程编排 |
| `app/evaluators/base.py` | 552 | 评估器基类 + 轨迹提取 + LLM 三级降级 |
| `app/graphs/evaluation_graph.py` | -- | evaluate_parallel / evaluate_partial |

### 建议读（⭐⭐）

| 文件 | 行数 | 核心职责 |
|---|---|---|
| `app/evaluators/planning_evaluator.py` | 241 | 规划质量评估 |
| `app/evaluators/tactical_evaluator.py` | 291 | 战术决策评估 |
| `app/evaluators/tool_use_evaluator.py` | -- | 工具使用评估 |
| `app/evaluators/memory_evaluator.py` | 252 | 记忆管理评估 |
| `app/evaluators/replan_evaluator.py` | 313 | 重规划评估 |
| `app/evaluators/retrieval_evaluator.py` | 220 | 检索质量评估 |
| `app/evaluators/trajectory_compressor.py` | -- | 4 阶段轨迹压缩 |

### 阅读路径

```
evaluation.py  _run_evaluation_background()
  → use_stream=false 时由 FastAPI BackgroundTasks 触发（无 Celery）

evaluation_service.py  run_evaluation()
  → 加载轨迹
  → 创建 / 复用 Evaluation 记录
  → evaluate_parallel()

evaluation_graph.py  evaluate_parallel()
  → asyncio.gather 并发 6 个评估器
  → 每个评估器调 evaluate()

base.py  _format_trajectory()
  → TrajectoryCompressor.compress() 4 阶段压缩
  → 返回压缩后的文本

base.py  LLM 调用链
  → prompt | llm + Pydantic / JSON 解析（无死路径 structured_output 包装）

evaluation_service.py  _persist_evaluation_results()
  → 加权聚合
  → 写入数据库；任务标 completed
```

---

## 三、SDK 采集层（连接两个 Agent 的桥梁）

### 必读（⭐⭐⭐）

| 文件 | 行数 | 核心职责 |
|---|---|---|
| `sdk/collector.py` | 1204 | 轨迹采集单例 + 缓冲 + 批量上传 + 重试 |
| `sdk/adapters/langgraph.py` | 428 | 自动包装节点 + _events 排出 + flush |
| `sdk/schemas.py` | 275 | 14 种 Pydantic Schema |

### 阅读路径

```
langgraph.py:185  _wrap_node_async()
  → 自动：NODE_EXECUTE(input)
  → 调节点函数
  → drain _events → collector.record()
  → 自动：NODE_EXECUTE(output)
  → 自动：STATE_CHANGE
  → auto _flush()

collector.py:678  record()
  → _validate_step() Pydantic 校验
  → 构建 step dict
  → 追加到缓冲区

collector.py:556  _flush()
  → POST /api/v1/tasks/{task_id}/trajectory
  → 失败回退到缓冲区
```

---

## 四、30 分钟快速阅读路线

按顺序读以下 6 个函数，覆盖全链路：

```
 1. graph.py:391      search 节点 — 看 plan 生成 + _events 构建
 2. langgraph.py:185  _wrap_node_async — 看 auto 采集 + _events 排出
 3. collector.py:678  record() — 看轨迹步骤格式
 4. evaluation_graph.py:416  evaluate_parallel — 看 6 维并发
 5. base.py:194      _extract_plans — 看评估器怎么过滤 TOOL_CALL
 6. evaluation_service.py:335  run_evaluation — 看全流程编排
```

---

## 五、各文件职责速查

```
app/
├── wiki_agent/
│   ├── agent/
│   │   ├── graph.py              LangGraph 编排（search → respond → decide → execute）
│   │   ├── context_retriever.py   四路记忆统一检索
│   │   ├── knowledge_agent.py     LLM 决定 CRUD 操作
│   │   ├── llm_factory.py         LLM 实例创建
│   │   └── tools/
│   │       ├── query_rewriter.py  Query 复杂度分级 + 改写
│   │       ├── search_tools.py    Milvus + BM25 + RRF + Rerank
│   │       ├── crud_tools.py      知识库 CRUD 操作
│   │       ├── vector_store.py    Milvus 索引管理
│   │       ├── bm25_index.py      BM25 索引管理
│   │       ├── reranker.py        Cross-Encoder 重排
│   │       ├── chunker.py         文档切分
│   │       ├── embeddings.py      Embedding 计算
│   │       └── sync_manager.py    知识库同步 + 一键重建
│   ├── routers/
│   │   ├── chat.py                SSE 流式对话 API
│   │   ├── wiki.py                知识库 CRUD API
│   │   ├── debug.py               调试/诊断 API
│   │   └── vector_admin.py        向量管理 API
│   └── session/
│       └── store.py               用户级/会话级记忆
│
├── evaluators/
│   ├── base.py                    评估器基类 + 轨迹提取 + LLM 调用
│   ├── trajectory_compressor.py   4 阶段轨迹压缩
│   ├── planning_evaluator.py      规划质量评估
│   ├── tactical_evaluator.py      战术决策评估
│   ├── tool_use_evaluator.py      工具使用评估
│   ├── memory_evaluator.py        记忆管理评估
│   ├── replan_evaluator.py        重规划评估
│   ├── retrieval_evaluator.py     检索质量评估
│   ├── consensus.py               多模型共识
│   ├── scoring.py                 加权聚合
│   └── eval_schemas.py            评估输出 Schema
│
├── graphs/
│   └── evaluation_graph.py        evaluate_parallel / evaluate_partial
│
├── services/
│   ├── evaluation_service.py      评估业务编排
│   ├── incremental_eval.py        增量评估
│   ├── regression_detection.py    回归检测
│   ├── replay_service.py          轨迹重放
│   └── judge_service.py           LLM Judge 调用
│
├── api/v1/endpoints/
│   ├── tasks.py                   任务 CRUD + 轨迹上传
│   ├── evaluation.py              评估触发 + 结果查询 + SSE
│   ├── reports.py                 报告导出
│   ├── benchmark.py               基准测试
│   └── system.py                  健康检查
│
├── db/
│   ├── models.py                  ORM 模型（AgentTask / Trajectory / Evaluation）
│   └── database.py                SQLAlchemy 引擎
│
└── core/
    ├── config.py                  配置（DEBUG / API Keys / 模型选择）
    ├── cache.py                   Redis 缓存
    ├── tracing.py                 OpenTelemetry 链路追踪
    └── metrics.py                 Prometheus 指标

sdk/
├── collector.py                   轨迹采集器单例
├── schemas.py                     14 种 Pydantic Schema
├── adapters/
│   ├── langgraph.py               LangGraph 自动包装
│   ├── callback.py                LangChain Callback 采集
│   └── llm_proxy.py               LLM 透明代理采集

docs/
├── architecture-data-flow.md      完整架构图 + 数据流 + 断点指南
├── project-issues.md              项目问题记录与解决方案
└── ...
```
