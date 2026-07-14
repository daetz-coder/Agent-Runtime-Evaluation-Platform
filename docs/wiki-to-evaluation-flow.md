# Wiki Agent → 评估平台：完整架构与数据流

> 从 Wiki 对话、轨迹采集、LLM 调用、队列推送到评估出分的端到端数据流动说明。  
> 基于当前实现：`async collector`、`HITL interrupt` 检测、`evaluation_task` SSE 事件。

相关文档：[architecture-data-flow.md](./architecture-data-flow.md) · [two-flow-architecture.md](./two-flow-architecture.md) · [data-collection-architecture.md](./data-collection-architecture.md)

---

## 一、系统架构总览

```mermaid
flowchart TB
    subgraph Client["前端 Vue"]
        CV[ChatView.vue<br/>Wiki 对话 SSE]
        TV[Tasks.vue / TaskDetail.vue]
        EV[EvaluationDetail.vue<br/>评估 SSE]
    end

    subgraph FastAPI["FastAPI 统一进程 :8000"]
        subgraph WikiAPI["Wiki Agent API"]
            CHAT["/api/chat/stream"]
            CONF["/api/chat/confirm"]
            SESS[(session_store<br/>SQLite sessions/messages)]
        end

        subgraph EvalAPI["评估平台 API /api/v1"]
            TASKS["POST /tasks/"]
            TRAJ["POST /tasks/{id}/trajectory"]
            EVAL_CREATE["POST /evaluations/"]
            EVAL_STREAM["POST /evaluations/stream"]
        end

        subgraph WikiCore["Wiki Agent 核心"]
            GRAPH[LangGraph<br/>search→respond→decide→execute]
            CKPT[(checkpoints.db<br/>LangGraph Checkpoint)]
            CTX[context_retriever<br/>Milvus + Memory]
            LLM_W[chat_llm / knowledge_agent<br/>DeepSeek 等]
        end

        subgraph EvalCore["评估核心"]
            ES[EvaluationService]
            EVGraph[evaluation_graph<br/>6 维 Evaluator]
            JUDGE[Judge LLM × 6]
        end

        subgraph SDK["sdk.collector"]
            COL[TrajectoryCollector<br/>ContextVar 会话隔离]
            BUF[内存缓冲 steps]
        end
    end

    subgraph Storage["持久化"]
        DB[(agent_eval.db<br/>tasks / trajectories / evaluations)]
        REDIS[(Redis<br/>cache / stream claim)]
        MILVUS[(Milvus<br/>知识库向量)]
    end

    subgraph Optional["非流式后台"]
        BG[FastAPI BackgroundTasks<br/>_run_evaluation_background]
    end

    CV -->|SSE| CHAT
    CV -->|confirm| CONF
    TV --> EVAL_CREATE
    EV --> EVAL_STREAM

    CHAT --> GRAPH
    CHAT --> SESS
    CONF --> GRAPH

    GRAPH --> CKPT
    GRAPH --> CTX
    GRAPH --> LLM_W
    GRAPH --> COL
    CTX --> MILVUS

    COL --> BUF
    COL -->|async HTTP| TASKS
    COL -->|async HTTP| TRAJ

    TASKS --> DB
    TRAJ --> DB
    EVAL_CREATE --> DB
    EVAL_STREAM --> ES
    ES --> DB
    ES --> EVGraph
    EVGraph --> JUDGE
    EVAL_CREATE -.->|use_stream=false| BG
    BG --> ES
    ES --> REDIS
    EVAL_STREAM --> REDIS
```

### 组件职责速查

| 组件 | 路径 | 职责 |
|------|------|------|
| ChatView | `app/wiki_agent/frontend/src/wiki/components/ChatView.vue` | 消费对话 SSE，展示流式回复与评估链接 |
| chat router | `app/wiki_agent/routers/chat.py` | 会话管理、SSE 封装、`evaluation_task` 事件 |
| LangGraph | `app/wiki_agent/agent/graph.py` | search→respond→decide→execute 编排 |
| Collector | `sdk/collector.py` | 轨迹缓冲、HTTP 上报 task/trajectory |
| Evaluation API | `app/api/v1/endpoints/evaluation.py` | 创建评估、SSE 流式评估 |
| EvaluationService | `app/services/evaluation_service.py` | 读轨迹、跑 6 维评估、持久化分数 |

---

## 二、端到端数据流（主路径）

**典型路径**：Wiki 流式对话 → 获取 `task_id` → 用户在 Tasks 页手动评估 → SSE 实时出分。

```mermaid
sequenceDiagram
    autonumber
    participant U as 用户浏览器
    participant CV as ChatView.vue
    participant Chat as /api/chat/stream
    participant Sess as session_store
    participant Graph as LangGraph
    participant Col as TrajectoryCollector
    participant API as 评估 API
    participant DB as agent_eval.db
    participant TV as Tasks / Eval UI
    participant Eval as /evaluations/stream
    participant Judge as Judge LLM ×6

    U->>CV: 输入消息
    CV->>Chat: POST /api/chat/stream {session_id, message}

    Chat->>Sess: 加载 history / 写入 user 消息
    Chat->>Graph: run_chat_stream()

    Note over Graph,Col: ① 创建评估 Task
    Graph->>Col: await start(goal, {thread_id, mode:stream})
    Col->>API: POST /api/v1/tasks/
    API->>DB: INSERT agent_tasks (id, goal, context, pending)
    API-->>Col: task_id
    Col->>Col: record(PLAN) → 内存 buffer

    Note over Graph: ② LangGraph 执行（见第三节）
    Graph-->>Chat: queue 事件 (content/wiki_results/extraction)
    Chat-->>CV: SSE data: {...}

    Note over Graph,Col: ③ 对话结束 — 轨迹落库，任务保持 pending
    Graph->>Col: finish(auto_run=False) 或 _flush() (HITL)
    Col->>API: POST /tasks/{id}/trajectory
    API->>DB: INSERT agent_trajectories
    Note over Col,DB: auto_run=False 不改 status，仍为 pending

    Chat->>Col: get_collector().task_id
    Chat-->>CV: SSE evaluation_task {task_id}
    Chat-->>CV: SSE done
    Chat->>Sess: 保存 assistant 消息

    U->>TV: 任务管理中显示「待处理」→ 点击「评估」
    TV->>API: POST /evaluations/ {task_id, use_stream:true}
    API->>DB: INSERT evaluations (in_progress)
    API-->>TV: evaluation_id
    TV->>Eval: POST /evaluations/stream {task_id, evaluation_id}

    Eval->>DB: SELECT agent_trajectories
    par 6 维并行
        Eval->>Judge: PlanningEvaluator
        Eval->>Judge: TacticalEvaluator
        Eval->>Judge: ToolUseEvaluator
        Eval->>Judge: MemoryEvaluator
        Eval->>Judge: ReplanEvaluator
        Eval->>Judge: RetrievalEvaluator
    end
    Eval-->>TV: SSE progress / result / done
    Eval->>DB: UPDATE evaluations (scores, completed)
```

---

## 三、LangGraph 节点级数据流

```mermaid
flowchart TD
    START([用户消息进入]) --> START_COL

    START_COL["collector.start()<br/>POST /tasks/ → task_id<br/>record(PLAN)"]
    START_COL --> SEARCH

    subgraph SEARCH["节点: search"]
        S1["_generate_plan() → LLM #1<br/>record(plan)"]
        S2["retrieve_context()<br/>Milvus 混合检索 + user/session memory"]
        S3["_extract_key_facts() → LLM #2<br/>record(retrieval/memory/evidence)"]
        S4["asyncio.create_task 写 session_store"]
        S5["collector._flush() → POST trajectory"]
        S1 --> S2 --> S3 --> S4 --> S5
    end

    SEARCH --> RESPOND

    subgraph RESPOND["节点: respond"]
        R1["chat_llm.astream() → LLM #3 流式"]
        R2["每 token → asyncio.Queue<br/>type: content"]
        R3["Queue → run_chat_stream yield<br/>→ Chat SSE → 前端逐字显示"]
        R4["record(EVIDENCE final_response)"]
        R5["collector._flush()"]
        R1 --> R2 --> R3
        R1 --> R4 --> R5
    end

    RESPOND --> COND1{ai_response<br/>长度 > 50?}

    COND1 -->|否| END1([END 无 decide])
    COND1 -->|是| DECIDE

    subgraph DECIDE["节点: decide"]
        D1["knowledge_agent.decide_action() → LLM #4"]
        D2["record(tool_decision/plan_update)"]
        D1 --> D2
    end

    DECIDE --> COND2{action != none?}

    COND2 -->|否| FINISH1["finish()<br/>flow_completed=true"]
    COND2 -->|是| EXECUTE

    subgraph EXECUTE["节点: execute — HITL"]
        E1["record(node_execute execute)"]
        E2["interrupt({})<br/>LangGraph 暂停"]
        E3["Queue → type: extraction<br/>含 thread_id"]
        E4["仅 collector._flush()<br/>hitl_pending=true"]
        E1 --> E2 --> E3 --> E4
    end

    EXECUTE --> HITL_WAIT([等待用户确认])

    HITL_WAIT -->|POST /api/chat/confirm| RESUME

    subgraph RESUME["resume_and_execute"]
        RS1["collector.attach(eval_task_id)<br/>从 checkpoint 读 task_id"]
        RS2["graph.ainvoke(Command(resume=confirm))"]
        RS3["CRUD tools create/update/delete"]
        RS4["record(tool_call/tool_result/replan)"]
        RS5["collector.finish()"]
        RS1 --> RS2 --> RS3 --> RS4 --> RS5
    end

    RESUME --> END2([END])
    FINISH1 --> END2
    END1 --> END2

    END2 --> EVAL_TASK["chat.py 发送 evaluation_task SSE<br/>task_id 给前端"]
```

### 各节点 LLM 调用一览

| 节点 | LLM 调用 | 轨迹 record 类型 |
|------|----------|------------------|
| search | `_generate_plan`、`_extract_key_facts` | plan, retrieval, memory_read/write, evidence, node_execute, state_change |
| respond | `chat_llm.astream` | evidence(final_response), node_execute, state_change |
| decide | `knowledge_agent.decide_action` | tool_decision, plan_update, node_execute |
| execute | 无（CRUD 工具） | tool_call, tool_result, replan, failure |

### LangGraph 拓扑

```
search → respond → should_decide? → decide → should_execute? → execute → END
                      ↓ end                              ↓ end
                     END                                 END
```

---

## 四、双队列机制（对话 SSE vs 评估 SSE）

系统中有两条独立的 **asyncio.Queue + SSE** 管道，互不干扰。

```mermaid
flowchart LR
    subgraph ChatPipeline["对话 SSE 管道"]
        Q1["asyncio.Queue<br/>(graph config event_queue)"]
        N1["respond/decide 节点<br/>_emit(queue, event)"]
        R1["run_chat_stream<br/>while queue.get() yield"]
        S1["chat.py stream_response<br/>data: JSON\\n\\n"]
        F1["ChatView.vue"]
        N1 --> Q1 --> R1 --> S1 --> F1
    end

    subgraph EvalPipeline["评估 SSE 管道"]
        Q2["asyncio.Queue<br/>(evaluation_stream 内部)"]
        N2["6 × run_eval 协程"]
        R2["event_generator"]
        S2["EventSourceResponse"]
        F2["EvaluationDetail.vue"]
        N2 --> Q2 --> R2 --> S2 --> F2
    end
```

| 队列 | 生产者 | 消费者 | SSE 端点 | 事件类型 |
|------|--------|--------|----------|----------|
| `event_queue` | respond / decide 节点 | `run_chat_stream` | `POST /api/chat/stream` | `content`, `wiki_results`, `status`, `extraction`, `evaluation_task`, `done`, `error` |
| eval `queue` | 6 个 Evaluator 协程 | `evaluation_stream` | `POST /api/v1/evaluations/stream` | `progress`, `result`, `error`, `done` |

### 对话 SSE 事件格式示例

```json
{"type": "content", "text": "JWT 是..."}
{"type": "wiki_results", "results": "- 向量索引 (wiki/...): ..."}
{"type": "extraction", "data": {"action": "create", "title": "...", "thread_id": "..."}}
{"type": "evaluation_task", "task_id": "550e8400-e29b-41d4-a716-446655440000"}
{"type": "done"}
```

---

## 五、TrajectoryCollector 数据流

```mermaid
flowchart TD
    subgraph AgentRuntime["Agent 运行时（同进程）"]
        REC["record() / record_*()<br/>sync，纯内存"]
        BUF["_CollectorSession.steps<br/>ContextVar 按请求隔离"]
        REC --> BUF
    end

    subgraph FlushTriggers["flush 触发点"]
        F1["search 节点结束 _flush()"]
        F2["respond 节点结束 _flush()"]
        F3["HITL interrupt 仅 _flush()"]
        F4["finish() 最终 _flush()"]
    end

    BUF --> F1 & F2 & F3 & F4
    F1 & F2 & F3 & F4 --> HTTP

    subgraph HTTP["async HTTP (httpx.AsyncClient)"]
        POST_T["POST /api/v1/tasks/{id}/trajectory"]
        PUT_S["PUT /api/v1/tasks/{id} status<br/>(仅 auto_run=True→completed / flush 失败→failed)"]
        POST_E["POST /api/v1/evaluations/ (仅 auto_run=true 且 flush 成功)"]
    end

    HTTP --> DB

    subgraph DB["SQLite agent_eval.db"]
        T1["agent_tasks（Wiki 默认保持 pending）"]
        T2["agent_trajectories"]
        T3["evaluations"]
    end

    POST_T --> T2
    PUT_S --> T1
    POST_E --> T3
```

### 单步 trajectory 结构

```json
{
  "step_number": 3,
  "action_type": "retrieval",
  "action_detail": {
    "query": "JWT 认证原理",
    "retrieved_docs": [{"title": "...", "path": "...", "snippet": "..."}]
  },
  "observation": null,
  "timestamp": "2026-07-13T12:00:00+00:00"
}
```

### Collector API 分层

| 类型 | 方法 | 说明 |
|------|------|------|
| async（含网络 I/O） | `start()`, `finish()`, `_flush()` | 须在 async 函数中 `await` |
| sync（纯内存） | `record()`, `record_*()`, `attach()` | LangGraph 节点 / LangChain 回调内直接调用 |

---

## 六、ID 流转

```mermaid
flowchart LR
    subgraph IDs["关键 ID"]
        SID["session_id<br/>Wiki 聊天会话"]
        TID["thread_id<br/>LangGraph checkpoint 键"]
        TASK["task_id<br/>评估任务 UUID"]
        EVAL["evaluation_id<br/>单次评估 UUID"]
    end

    SID --> CHAT["/api/chat/stream"]
    TID --> GRAPH["LangGraph config"]
    TID --> CTX["task.context.thread_id"]
    TASK --> FRONT1["evaluation_task SSE"]
    TASK --> FRONT2["/tasks/{task_id}"]
    TASK --> EVAL_CREATE["POST /evaluations/"]
    EVAL --> FRONT3["/evaluations/{id}?stream=1"]

    TID -.->|"state.eval_task_id"| TASK
    TID -.->|"HITL resume attach()"| COL[collector]
```

| ID | 生成位置 | 用途 |
|----|----------|------|
| `session_id` | 前端 / 默认 `"default"` | Wiki 多轮对话、消息历史（`session_store`） |
| `thread_id` | `run_chat_stream` 内 `uuid4()` | LangGraph checkpoint；写入 `task.context` |
| `task_id` | `collector.start()` → `POST /tasks/` | 轨迹容器；评估输入；前端评估链接 |
| `evaluation_id` | `POST /evaluations/` | 单次评估记录；SSE stream 参数 |

---

## 七、评估阶段详细数据流

```mermaid
flowchart TD
    TRIGGER["触发评估<br/>Tasks 页 / API"] --> MODE{use_stream?}

    MODE -->|true — UI 默认| STREAM
    MODE -->|false| BG

    subgraph STREAM["SSE 评估路径"]
        S1["POST /evaluations/<br/>create_evaluation → IN_PROGRESS"]
        S2["POST /evaluations/stream"]
        S3["DB 直接读 agent_trajectories"]
        S4["try_claim_stream (Redis)<br/>防重复 LLM"]
        S5["6 协程并行 Evaluator.evaluate()"]
        S6["每个 Evaluator → Judge LLM"]
        S7["asyncio.Queue → SSE progress"]
        S8["finalize_from_parallel → DB"]
        S9["SSE result + done"]
        S1 --> S2 --> S3 --> S4 --> S5 --> S6 --> S7 --> S8 --> S9
    end

    subgraph BG["非流式后台路径"]
        C1["POST /evaluations/ use_stream=false"]
        C2["BackgroundTasks._run_evaluation_background"]
        C3["EvaluationService.run_evaluation"]
        C4["evaluate_parallel 6 维"]
        C5["UPDATE evaluations COMPLETED"]
        C1 --> C2 --> C3 --> C4 --> C5
    end

    S8 --> RESULT[(evaluations 表)]
    C5 --> RESULT
```

### Evaluator 输入 / 输出

**输入：**

- `goal` ← `agent_tasks.goal`
- `trajectory` ← `agent_trajectories[]`（按 `step_number` 排序）
- `context` ← `agent_tasks.context`

**输出（写入 `evaluations`）：**

- `planning_score` / `planning_feedback`
- `tactical_score` / `tactical_feedback`
- `tool_use_score` / `tool_use_feedback`
- `memory_score` / `memory_feedback`
- `replan_score` / `replan_feedback`
- `retrieval_score` / `retrieval_feedback`
- `overall_score`
- `status = completed`

### 评估 SSE 事件示例

```
event: progress
data: {"dimension":"planning","score":78.0,"progress":1,"total":6}

event: result
data: {"scores":{"planning":78,...},"overall":72.5,"evaluation_id":"..."}

event: done
data: {}
```

---

## 八、HITL 分支时序（知识库 CRUD 确认）

```mermaid
sequenceDiagram
    participant U as 用户
    participant CV as ChatView
    participant G as LangGraph
    participant C as Collector
    participant DB as agent_eval.db

    G->>G: decide → action=create
    G->>G: execute → interrupt()
    G->>C: _flush() 仅上传已有步骤
    Note over G: aget_state().interrupts 非空 → hitl_pending=true
    G-->>CV: extraction {thread_id, title, content...}
    Note over U,CV: 用户看到「确认保存知识」卡片

    U->>CV: 点击确认
    CV->>G: POST /api/chat/confirm {thread_id, confirm:true}
    G->>C: attach(eval_task_id) 从 checkpoint
    G->>G: Command(resume=true)
    G->>G: execute CRUD tool
    G->>C: record(tool_call/tool_result)
    G->>C: finish(auto_run=False) → 追加轨迹，任务仍 pending
    C->>DB: 追加 execute 阶段 steps
```

**要点：**

- interrupt 时 **不** 调用 `finish()`，只 `_flush()`，避免在 HITL 未结束时结束会话。
- 对话/resume 正常结束调用 `finish(auto_run=False)`：只 flush 轨迹，**不**标 completed、**不**自动评估；任务管理显示「待处理」。
- `search` 节点将 `eval_task_id` 写入 state，供 `resume_and_execute` 中 `collector.attach()` 复用同一 task。
- `attach()` **不** 重置 `eval_triggered`，避免重复触发评估。

---

## 九、存储层一览

```mermaid
flowchart TB
    subgraph WikiStore["Wiki 侧存储"]
        WS1["sessions 表<br/>id, name, key_facts"]
        WS2["messages 表<br/>role, content, wiki_results, extraction"]
        WS3["checkpoints.db<br/>LangGraph 状态 + eval_task_id"]
        WS4["Milvus<br/>知识库向量"]
    end

    subgraph EvalStore["评估侧存储 agent_eval.db"]
        ES1["agent_tasks<br/>id, goal, context, status"]
        ES2["agent_trajectories<br/>task_id, step_number, action_type, ..."]
        ES3["evaluations<br/>6维分数, overall, status"]
    end

    subgraph Cache["Redis 可选"]
        RC1["trajectory:{task_id}"]
        RC2["stream:claim:{eval_id}"]
        RC3["task:/dashboard: cache"]
    end

    COL[TrajectoryCollector] --> ES1 & ES2
    GRAPH[LangGraph] --> WS3
    SESS[session_store] --> WS1 & WS2
    CTX[retrieve_context] --> WS4
    EVAL[EvaluationService] --> ES3
    EVAL -.-> RC1 & RC2
```

| 存储 | 文件 / 服务 | 生命周期 |
|------|-------------|----------|
| Wiki 会话 | `app/wiki_agent/data/` SQLite | 用户聊天历史、key_facts |
| LangGraph Checkpoint | `checkpoints.db` | HITL 暂停 / resume |
| 评估 Task | `agent_eval.db` → `agent_tasks` | 一次 Agent 运行 |
| 轨迹 Steps | `agent_eval.db` → `agent_trajectories` | 随 task 持久化 |
| 评估结果 | `agent_eval.db` → `evaluations` | 每次评估一条记录 |
| 向量库 | Milvus | 知识库检索 |

---

## 十、关键设计要点

1. **Wiki 对话默认不 auto_run 评估**：`finish(auto_run=False)` 只上报轨迹，任务保持 `pending`；用户在 Tasks 页手动点「评估」。
2. **轨迹先于评估**：评估从 DB 读 `agent_trajectories`；空轨迹会导致全 0 分。`auto_run=True` 时仅在 `flush_succeeded` 后触发。
3. **同进程 HTTP 上报**：Collector 通过 `EVAL_API_BASE_URL`（默认 `http://127.0.0.1:8000`）调用自身 FastAPI。
4. **ContextVar 会话隔离**：并发 Wiki 对话共享 Collector 单例，但各自独立 `task_id` / buffer。
5. **两条 SSE 独立**：对话流（token 级）与评估流（维度级）使用不同 Queue 与端点。
6. **中途 flush**：search / respond 节点结束后 `_flush()`，降低长对话轨迹丢失风险。
7. **非流式评估**：`use_stream=false` 时用 FastAPI `BackgroundTasks`，已移除 Celery。

---

## 十一、代码入口索引

| 阶段 | 文件 | 函数 / 端点 |
|------|------|-------------|
| 前端发消息 | `app/wiki_agent/frontend/.../ChatView.vue` | `sendMessage()` → `POST /api/chat/stream` |
| 对话 SSE | `app/wiki_agent/routers/chat.py` | `stream_response()` |
| 图编排 | `app/wiki_agent/agent/graph.py` | `run_chat_stream()`, `resume_and_execute()` |
| 创建 task | `sdk/collector.py` | `await start()` → `POST /api/v1/tasks/` |
| 上报轨迹 | `sdk/collector.py` | `await _flush()` → `POST /api/v1/tasks/{id}/trajectory` |
| 创建评估 | `app/api/v1/endpoints/evaluation.py` | `POST /evaluations/` |
| 流式评估 | `app/api/v1/endpoints/evaluation.py` | `POST /evaluations/stream` |
| 持久化轨迹 | `app/services/evaluation_service.py` | `add_trajectory()` |
| 跑评估 | `app/services/evaluation_service.py` | `run_evaluation()` / `finalize_from_parallel()` |

---

## 十二、诊断日志

启用后可在日志中追踪完整链路（前缀 `[EvalDiag]`）：

```
[EvalDiag] start task_id=... remote task created
[EvalDiag] _flush POST task_id=... steps=N
[EvalDiag] trajectory persisted task_id=... added=N total=M
[EvalDiag] finish after flush steps_remaining=0
[EvalDiag] SSE /evaluations/stream trajectory_steps=M
[EvalDiag] evaluator dim=planning llm_calls=1 elapsed_ms=3000+
```

若出现 `trajectory_steps=0` 或 `BUG PATH: auto_run triggered AFTER flush failure`，说明轨迹未入库或 flush 失败，需检查 `EVAL_API_BASE_URL` 与网络连通性。
