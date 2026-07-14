# 系统架构与数据流

> 从用户提问 → Agent 处理 → 轨迹采集 → 评估平台，完整的数据流动链路。

**完整详图（含 Mermaid 架构图 / 时序图 / ID 流转）**：请参阅 [wiki-to-evaluation-flow.md](./wiki-to-evaluation-flow.md)

---

## 一、架构总览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          用户层                                          │
│   用户 ──→ Vue3 前端 (SSE 实时推送)                                      │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │ POST /api/chat/stream
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        FastAPI 接口层 (app/api/v1/endpoints/)           │
│                                                                         │
│  chat.py          tasks.py            evaluation.py                     │
│  /api/chat/stream /api/v1/tasks/     /api/v1/evaluations/              │
│  /api/chat/invoke /tasks/{id}/trajectory  /evaluations/{id}/stream     │
└──────────┬──────────────────┬────────────────────┬──────────────────────┘
           │                  │                    │
           ▼                  ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     Wiki Agent (app/wiki_agent/agent/)                  │
│                                                                         │
│  graph.py:run_chat_stream()                                             │
│    │                                                                    │
│    ├─ instrument_langgraph(StateGraph)  ← 自动包装节点                   │
│    │                                                                    │
│    ├─ search 节点                                                       │
│    │   ├─ query_rewriter.py     → 复杂度分级 + Query 改写               │
│    │   ├─ context_retriever.py  → 四路记忆统一检索                      │
│    │   ├─ search_tools.py       → Milvus + BM25 + RRF + Cross-Encoder  │
│    │   └─ session/store.py      → User Memory + Session Memory         │
│    │                                                                    │
│    ├─ respond 节点                                                      │
│    │   └─ _build_llm_messages() → LLM 流式生成                          │
│    │                                                                    │
│    ├─ decide 节点                                                       │
│    │   └─ knowledge_agent.py    → 决定 CRUD 操作                       │
│    │                                                                    │
│    └─ execute 节点                                                      │
│        ├─ interrupt(HITL)       → 等待用户确认                          │
│        └─ crud_tools.py         → 创建/更新/删除知识条目                │
│                                                                         │
│  每个节点返回 _events → wrapper 统一排出 → collector.record()           │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │ POST /tasks/{id}/trajectory
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      SDK 轨迹采集层 (sdk/)                              │
│                                                                         │
│  collector.py:TrajectoryCollector     单例，ContextVar 会话隔离         │
│    ├─ start()           → POST /api/v1/tasks/  创建评估任务             │
│    ├─ record()          → 缓冲轨迹步骤到内存                            │
│    ├─ _flush()          → POST /api/v1/tasks/{id}/trajectory           │
│    └─ finish(auto_run)  → flush；False 保持 pending；True 则完成+评估  │
│                                                                         │
│  adapters/langgraph.py:InstrumentedStateGraph                           │
│    ├─ 自动: NODE_EXECUTE(input/output)                                  │
│    ├─ 自动: STATE_CHANGE (before/after diff)                            │
│    ├─ 自动: FAILURE (未捕获异常时)                                      │
│    ├─ drain _events → collector.record()                                │
│    └─ 节点级 _flush()                                                   │
│                                                                         │
│  schemas.py: 14 种 Pydantic Schema (统一校验)                           │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   评估平台服务层 (app/services/)                          │
│                                                                         │
│  evaluation_service.py:EvaluationService                                │
│    ├─ create_task()        → AgentTask 入库                             │
│    ├─ add_trajectory()     → AgentTrajectory 入库                       │
│    ├─ run_evaluation()     → 加载轨迹 → 6 维评估                        │
│    ├─ _persist_evaluation_results() → Evaluation 入库                   │
│    └─ get_evaluation()     → 查询评估结果                               │
│                                                                         │
│  replay_service.py         → 历史轨迹重放                               │
│  regression_detection.py   → 回归检测                                   │
│  incremental_eval.py       → 增量评估                                   │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    评估器层 (app/evaluators/)                            │
│                                                                         │
│  base.py:BaseEvaluator                                                  │
│    ├─ _is_tool(step, name)       → 按 tool_name 过滤 TOOL_CALL          │
│    ├─ _tool_input(step)          → 安全读取 input 子字段                │
│    ├─ _extract_plans()           → tool_name == "plan"                  │
│    ├─ _extract_tool_calls()      → tool_name 以 "crud_" 开头            │
│    ├─ _extract_replans()         → tool_name == "replan"                │
│    ├─ _extract_memory_events()   → tool_name in ("memory_write","read") │
│    ├─ _extract_retrievals()      → tool_name == "retrieval"             │
│    └─ _extract_evidence()        → tool_name in ("evidence","answer")   │
│                                                                         │
│  trajectory_compressor.py ← 4 阶段压缩管线                              │
│  planning_evaluator.py     ← 规划评估                                   │
│  tactical_evaluator.py     ← 战术决策评估                               │
│  tool_use_evaluator.py     ← 工具使用评估                               │
│  memory_evaluator.py       ← 记忆管理评估                               │
│  replan_evaluator.py       ← 重规划评估                                 │
│  retrieval_evaluator.py    ← 检索质量评估                               │
│  consensus.py              ← 多模型共识                                 │
│  scoring.py                ← 加权聚合                                   │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      数据持久化 (app/db/)                                │
│                                                                         │
│  models.py:                                                             │
│    AgentTask         → 评估任务元信息(id, goal, status, ...)            │
│    AgentTrajectory   → 轨迹步骤(step_number, action_type, detail, obs) │
│    Evaluation        → 评估结果(6维分数、总体分、反馈, ...)              │
│                                                                         │
│  database.py         → SQLAlchemy async engine                          │
│  SQLite / PostgreSQL                                                    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 二、数据流分阶段详解

### 阶段 1：用户输入 → Agent 响应

```
步骤  文件                         函数/方法                        数据内容
────  ─────────────────────────── ─────────────────────────────── ─────────────────────────

 ①    routers/chat.py             POST /api/chat/stream           {"session_id","message"}
      行 74: run_chat_stream()

 ②    chat.py                     _build_history()                [HumanMessage, AIMessage, ...]
      行 58: _ensure_session()                                    最多 HISTORY_MAX_TURNS 轮

 ③    agent/graph.py              run_chat_stream()               WikiState 初始化
      行 935: collector.start()                             POST /api/v1/tasks/ → task_id
      行 967: graph.ainvoke()                                     进入 InstrumentedCompiledGraph

 ④    sdk/collector.py            start()                   POST /api/v1/tasks/
      行 412: _new_session()                                      创建 AgentTask(PENDING)
             _http_with_retry()

 ⑤─── 进入 LangGraph search 节点 ──────────────────────────────────────────────────────

 ⑥    graph.py                    search()                        WikiState:user_message
      行 391: _generate_plan()                                    {"goal","steps","milestones"}

 ⑦    query_rewriter.py           rewrite_query()                 QueryComplexity
      行 64:                                                      rewritten_queries + complexity
      复杂度分级: TRIVIAL / SIMPLE / MEDIUM / COMPLEX

 ⑧    context_retriever.py        retrieve_context()              RetrievedContext
      行 51:                                                        ├─ wiki_results[]
      并行读取四路记忆:                                               ├─ user_facts[]
        - External KB:  hybrid_search()                            ├─ session_facts[]
        - User Memory:  get_user_memory()                          └─ history_summary
        - Session Mem:  get_session_key_facts()
        - Working Mem:  _summarize_history()

 ⑨    search_tools.py             hybrid_search()                 Milvus 语义检索
      行: query_rewriter 输出 →                                    BM25 关键词检索
          asyncio.to_thread() →                                    RRF 融合排序
          Milvus + BM25 → RRF → Rerank                            Cross-Encoder 重排

 ⑩    session/store.py            get_user_memory()               [{"content","type",...}]
      行:                           get_session_key_facts()        [{"content","type",...}]

 ⑪    graph.py                    search() 返回 _events           [
      行 469: _tc("plan", ...)                                       TOOL_CALL(tool_name="plan")
      行 490: _tc("retrieval", ...) + _tr(...)                       TOOL_CALL(tool_name="retrieval")
      行 504: _tc("memory_write", ...)                               TOOL_CALL(tool_name="memory_write")
      行 516: _tc("memory_read", ...) + _tr(...)                     TOOL_CALL(tool_name="memory_read")
      行 534: _tc("evidence", ...)                                   TOOL_CALL(tool_name="evidence")
      行 561: _tc("plan_update", ...)                                TOOL_CALL(tool_name="plan_update")
                                                                    ]

 ⑫─── 进入 LangGraph respond 节点 ─────────────────────────────────────────────────────

 ⑬    graph.py                    respond()                       stream LLM → collected
      行 588: _build_llm_messages()                                SystemPrompt + Context + History
             chat_llm.astream()

 ⑭    graph.py                    respond() 返回 _events           [
      行 615: _tc("final_answer", ...) + _tr(...)                    TOOL_CALL(tool_name="final_answer")
                                                                    ]

 ⑮─── 进入 LangGraph decide 节点 ────────────────────────────────────────────────────

 ⑯    graph.py                    decide()                        {"action","title",...}
      行 637: knowledge_agent.decide_action()

 ⑰    graph.py                    decide() 返回 _events           [
      行 651: ActionType.TOOL_DECISION                               TOOL_DECISION
      行 660: _tc("plan_update", ...)                                TOOL_CALL(tool_name="plan_update")
                                                                    ]

 ⑱─── 进入 LangGraph execute 节点 ────────────────────────────────────────────────────

 ⑲    graph.py                    execute()                       interrupt({}) → HITL
      行 672: user_confirmed = interrupt({})

 ⑳    crud_tools.py               create/update/delete_knowledge   操作结果 dict
      行:   asyncio.to_thread()

 ㉑    graph.py                    execute() 返回 _events           [
      行 677: _tc("replan", ...)          (用户取消时)                 TOOL_CALL(tool_name="replan")
      行 777: _build_tool_events(...)     (CRUD 成功时)               TOOL_CALL(tool_name="crud_*")
      行 789: FailureDetail(...)          (CRUD 异常时)               FAILURE
      行 819: _tc("replan", ...)          (REPLAN 时)                TOOL_CALL(tool_name="replan")
                                                                    ]
```

### 阶段 2：轨迹采集 → 评估平台

```
步骤  文件                         函数/方法                        数据内容
────  ─────────────────────────── ─────────────────────────────── ─────────────────────────

㉒    sdk/adapters/langgraph.py    _wrap_node_async()              自动记录:
      行 198: record_node_execute()                                  NODE_EXECUTE(input)
      行 209: drain _events                                          → collector.record() × N
      行 215: record_node_execute()                                  NODE_EXECUTE(complete)
      行 217: record_state_change()                                  STATE_CHANGE
      行 220: _flush()                                         上传到平台

㉓    sdk/collector.py             record()                        构建 step dict:
      行 678: _validate_step()                                       {"step_number",
      行 722: session.steps.append()                                  "action_type",
                                                                      "action_detail",
                                                                      "observation",
                                                                      "timestamp"}

㉔    sdk/collector.py             _flush()                   POST /api/v1/tasks/
      行 556: _http_with_retry()                              {task_id}/trajectory
      批量发送缓冲区的全部 steps                                       [step, step, step, ...]

㉕    api/v1/endpoints/tasks.py    POST /tasks/{id}/trajectory      [TrajectoryStep, ...]
      行 98: add_trajectory()
      行 117: EvaluationService.add_trajectory()

㉖    services/evaluation_service.py add_trajectory()               INSERT INTO agent_trajectories
      行: _add_trajectory_steps()                                    (task_id, step_number,
                                                                      action_type, action_detail,
                                                                      observation, timestamp)

㉗    sdk/collector.py             finish(auto_run=...)             Wiki: auto_run=False
      最后一次 flush；仅 auto_run=True 时                               → 任务保持 pending
      标 completed 并 POST /evaluations/                              手动评估走 Tasks UI

㉘    api/v1/endpoints/evaluation.py POST /evaluations/             EvaluationRequest
      create_evaluation()                                            {"task_id", use_stream}
      use_stream=false → BackgroundTasks                             _run_evaluation_background
```

### 阶段 3：评估执行 → 结果入库

```
步骤  文件                         函数/方法                        数据内容
────  ─────────────────────────── ─────────────────────────────── ─────────────────────────

㉙    services/evaluation_service.py run_evaluation()               Evaluation(IN_PROGRESS)
      行 335: _get_trajectory()                                     [trajectory steps]
             get_evaluation() / create Evaluation

㉚    evaluation_graph.py         evaluate_parallel()               asyncio.gather × 6
      行 420:                                                       planning_evaluator
                                                                    tactical_evaluator
                                                                    tool_use_evaluator
                                                                    memory_evaluator
                                                                    replan_evaluator
                                                                    retrieval_evaluator

㉛    base.py                     每个评估器的 evaluate()           TrajectoryStep 列表
      行 165: _format_trajectory()
      行 178: TrajectoryCompressor.compress()

㉜    trajectory_compressor.py    4 阶段压缩                       ↓ 压缩后文本
      行 49: compress()                                             ① Importance Filter
      行 72: _importance_filter()                                   ② Think Summary
      行 80: _summarize_thinks()                                    ③ Recent Window
      行 97: _recent_window()                                       ④ Context Builder
      行 119: _build_context()

㉝    base.py                     _invoke_structured_llm()          LLM 调用
      行 349: 三级降级:                                               ① with_structured_output
             _try_structured_output()                                ② PydanticOutputParser
             _try_pydantic_parser()                                  ③ 手动 JSON 解析
             _try_manual_parse()

㉞    scoring.py                  weighted_overall()                加权综合分
      行: score_values()                                            {"planning":85, "tactical":72, ...}
           weighted_overall()                                       overall=78.5

㉟    services/evaluation_service.py _persist_evaluation_results()   UPDATE Evaluation
      行 455:                                                       (COMPLETED + 6维分数)

㊱    evaluation.py               GET /evaluations/{id}             EvaluationResponse
      行: stream_evaluation()                                        SSE 推送进度
```

---

## 三、各阶段数据格式

### 3.1 WikiState（LangGraph 状态）

```python
class WikiState(TypedDict, total=False):
    user_message: str               # 用户原始输入
    wiki_results: list[dict]        # 检索到的知识库文档
    wiki_text: str | None           # 格式化的文档文本（向后兼容）
    ai_response: str                # Agent 生成的回复
    decision: dict | None           # LLM 的 CRUD 决策
    action_result: dict | None      # CRUD 执行结果
    stage: str                      # 当前阶段: search / respond / decide / execute
    retrieved_context: dict | None  # 完整检索上下文
    eval_task_id: str | None        # 评估任务 ID（HITL 恢复用）
```

### 3.2 _events 事件格式（统一 TOOL_CALL）

所有域事件统一为 `TOOL_CALL` + `TOOL_RESULT`，`tool_name` 区分领域：

```python
# 通用 TOOL_CALL 格式
{
    "action_type": ActionType.TOOL_CALL,
    "action_detail": ToolCallDetail(
        tool_name="plan|retrieval|memory_write|memory_read|evidence|final_answer|plan_update|replan|crud_*",
        input={...},        # 领域特定参数
        duration_ms=...,    # 执行耗时（可选）
    ).model_dump(),
    "observation": ...,     # 执行结果（可选）
}

# 通用 TOOL_RESULT 格式（有明确输出时）
{
    "action_type": ActionType.TOOL_RESULT,
    "action_detail": ToolResultDetail(
        tool_name="...",
        success=True,
        duration_ms=...,
        error_type=None,
    ).model_dump(),
    "observation": ...,
}

# 自动记录（instrument_langgraph）
{
    "action_type": ActionType.NODE_EXECUTE,   # 或 STATE_CHANGE / FAILURE
    "action_detail": {...},
}
```

### 3.3 `tool_name` 完整对照表

| tool_name | 触发节点 | input 字段 | observation |
|---|---|---|---|
| `plan` | search | `goal`, `steps`, `milestones` | 无 |
| `retrieval` | search | `query`, `source`, `result_count` | 文档列表 |
| `memory_write` | search | `key`, `value`, `source`, `memory_type` | 无 |
| `memory_read` | search | `key`, `hit` | 读取结果（文本） |
| `evidence` | search | `evidence_type`, `sources` | 无 |
| `plan_update` | search/decide | `milestone_status`, `next_action`, `reason`, `remaining_steps` | 无 |
| `final_answer` | respond | `session_id`, `total_message_count` | 回答文本 |
| `replan` | execute | `reason`, `new_plan`, `trigger` | 无 |
| `crud_create/update/delete` | execute | `title`, `path` | 操作结果 |
| `crud_*_retry` | execute (重试) | `title`, `path` | 重试结果 |

### 3.4 评估数据库表结构

```sql
-- agent_tasks: 评估任务元信息
CREATE TABLE agent_tasks (
    id           VARCHAR(36) PRIMARY KEY,
    goal         TEXT NOT NULL,
    context      JSON,
    status       ENUM('pending','running','completed','failed','timeout'),
    created_at   DATETIME,
    started_at   DATETIME,
    completed_at DATETIME
);

-- agent_trajectories: 轨迹步骤
CREATE TABLE agent_trajectories (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id        VARCHAR(36) REFERENCES agent_tasks(id),
    step_number    INTEGER NOT NULL,
    action_type    VARCHAR(50) NOT NULL,   -- "tool_call" | "tool_result" | "failure" | "think" | ...
    action_detail  JSON NOT NULL,          -- {"tool_name": "plan", "input": {...}}
    observation    TEXT,
    timestamp      DATETIME
);

-- evaluations: 评估结果
CREATE TABLE evaluations (
    id                VARCHAR(36) PRIMARY KEY,
    task_id           VARCHAR(36) REFERENCES agent_tasks(id),
    status            ENUM('pending','in_progress','completed','failed'),
    overall_score     FLOAT,
    -- 6 维分数 (JSON)
    planning_score    JSON,
    tactical_score    JSON,
    tool_use_score    JSON,
    memory_score      JSON,
    replan_score      JSON,
    retrieval_score   JSON,
    -- ...
);
```

---

## 四、断点调试指南

### 4.1 快速定位问题

```
问题现象                       优先检查的断点
──────────────────────────────────────────────────
Agent 没有响应                 A: chat.py 入口，看请求是否到达
轨迹步骤缺失                   B: langgraph.py 的 drain _events 位置
轨迹字段不对                   D: collector.py 的 record() 位置
评估器报错/分数异常            F: 各 evaluator 的 evaluate() 入口
前端看不到评估结果             G: evaluation_service.py 的 _persist 位置
HITL 恢复后数据丢失            C: execute 节点的 interrupt + resume
```

### 4.2 断点位置清单

```
断点  文件                   行号   条件
───  ────────────────────── ────── ────────────────────────────
A    chat.py                 74     run_chat_stream 入口
                                   查看: user_message, chat_history

B1   langgraph.py            195    _wrap_node_async 入口
                                   查看: node_name, state_before

B2   langgraph.py            204    节点执行后
                                   查看: result（_events 字段）

B3   langgraph.py            210    drain _events
                                   查看: 逐个 event 的 action_type + action_detail

C1   graph.py                421    search 节点检索结果
                                   查看: ctx.wiki_results, ctx.user_facts

C2   graph.py                469    search 节点 _events 构建
                                   查看: events 列表（6 个事件）

C3   graph.py                634    respond 节点完整回答
                                   查看: collected

C4   graph.py                696    decide 节点决策
                                   查看: decision_dict

C5   graph.py                759    execute 节点 CRUD 结果
                                   查看: result

D1   collector.py            678    record() 入口
                                   查看: action_type, action_detail

D2   collector.py            556    _flush()
                                   查看: steps_to_send 列表

D3   collector.py            546    finish()
                                   查看: flush_succeeded

E1   tasks.py                116    add_trajectory()
                                   查看: steps 列表长度和第一条的 action_type

E2   evaluation_service.py   334    run_evaluation()
                                   查看: trajectory 列表

F1   evaluation_service.py   436    evaluate_parallel()
                                   查看: 6 个评估器返回结果

F2   planning_evaluator.py   117    evaluate() 入口
                                   查看: goal, trajectory

F3   base.py                 194    _extract_plans()
                                   查看: step.action_type, tool_name

G1   evaluation_service.py   455    _persist_evaluation_results()
                                   查看: overall 字典
```

### 4.3 调试示例：轨迹字段不匹配

```python
# 在 collector.py:678 设置断点
# 检查每次 record() 调用

# 预期看到（统一 TOOL_CALL 格式）：
{
    "action_type": "tool_call",
    "action_detail": {
        "tool_name": "retrieval",       # ← 关键字段
        "input": {"query": "..."},      # ← 参数在 input 子字段
        "duration_ms": 120.5,
    },
    "observation": [{"title": "..."}],
}

# 如果看到旧格式（可能来自其他未统一代码）：
{
    "action_type": "retrieval",          # ← 旧格式：直接 action_type
    "action_detail": {
        "query": "...",                  # ← 旧格式：参数在顶层
    },
}
# → 检查这个 record() 调用的来源，找到未统一的代码
```

---

## 五、各文件职责速查

| 文件 | 职责 |
|---|---|
| `app/wiki_agent/routers/chat.py` | 对话 API 入口，SSE 流式输出，HITL 确认 |
| `app/wiki_agent/agent/graph.py` | LangGraph 编排（search → respond → decide → execute），轨迹事件构建 |
| `app/wiki_agent/agent/context_retriever.py` | 四路记忆统一检索（KB + User/Session/Working Memory） |
| `app/wiki_agent/agent/query_rewriter.py` | 复杂度分级 + Query 改写 + 余弦校验 |
| `app/wiki_agent/agent/knowledge_agent.py` | LLM 驱动的 CRUD 决策 |
| `app/wiki_agent/agent/tools/search_tools.py` | Milvus 语义检索 + BM25 关键词检索 + RRF + Rerank |
| `app/wiki_agent/agent/tools/crud_tools.py` | 知识库文档 CRUD 操作 |
| `app/wiki_agent/agent/tools/query_rewriter.py` | Query 改写逻辑 |
| `app/wiki_agent/session/store.py` | 用户级 / 会话级记忆持久化 |
| `sdk/collector.py` | 轨迹采集器单例，缓冲 + 批量上传 + 重试 |
| `sdk/schemas.py` | 14 种 Pydantic Schema |
| `sdk/adapters/langgraph.py` | LangGraph 自动包装（_events 排出 + 节点级 flush） |
| `app/evaluators/base.py` | 评估器基类：_is_tool()、轨迹提取、LLM 调用、缓存 |
| `app/evaluators/trajectory_compressor.py` | 4 阶段轨迹压缩管线 |
| `app/evaluators/planning_evaluator.py` | 规划质量评估 |
| `app/evaluators/tactical_evaluator.py` | 战术决策评估 |
| `app/evaluators/tool_use_evaluator.py` | 工具使用评估 |
| `app/evaluators/memory_evaluator.py` | 记忆管理评估 |
| `app/evaluators/replan_evaluator.py` | 重规划评估 |
| `app/evaluators/retrieval_evaluator.py` | 检索质量评估 |
| `app/evaluators/consensus.py` | 多模型共识评分 |
| `app/evaluators/scoring.py` | 加权聚合计算 |
| `app/services/evaluation_service.py` | 评估业务逻辑编排 |
| `app/graphs/evaluation_graph.py` | evaluate_parallel / evaluate_partial（asyncio.gather） |
| `app/db/models.py` | ORM 模型定义 |
| `app/api/v1/endpoints/tasks.py` | 任务 CRUD + 轨迹上传 API |
| `app/api/v1/endpoints/evaluation.py` | 评估触发 + 结果查询 + SSE 推送 |
