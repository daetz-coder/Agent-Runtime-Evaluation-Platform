# 评估平台数据采集架构 — 完整技术文档

> 本文档详细说明评估平台如何获取数据、获取哪些数据、为什么能获取、以及数据如何被消费。

---

## 目录

- [一、数据采集全景图](#一数据采集全景图)
- [二、四条数据采集路径](#二四条数据采集路径)
- [三、14 种轨迹数据类型详解](#三14-种轨迹数据类型详解)
- [四、核心代码逐行解析](#四核心代码逐行解析)
- [五、数据消费：6 个评估器](#五数据消费6-个评估器)
- [六、数据库表结构](#六数据库表结构)
- [七、为什么能获取到数据](#七为什么能获取到数据)

---

## 一、数据采集全景图

```
                    ┌─────────────────────────────────────────────┐
                    │              评估平台 (FastAPI)              │
                    │                                             │
                    │   ┌─────────────┐    ┌──────────────────┐  │
                    │   │  REST API   │    │  InProcess 直写   │  │
                    │   │  /tasks/    │    │  (同进程 DB)      │  │
                    │   └──────┬──────┘    └────────┬─────────┘  │
                    │          │                    │             │
                    │          ▼                    ▼             │
                    │   ┌─────────────────────────────────────┐  │
                    │   │       EvaluationService              │  │
                    │   │  add_trajectory() → DB 写入          │  │
                    │   │  run_evaluation() → 6 个评估器并行    │  │
                    │   └─────────────────────────────────────┘  │
                    └─────────────────────────────────────────────
                         ▲                    ▲
                         │ HTTP               │ 进程内直写
                         │                    │
          ┌──────────────┴──────┐    ┌────────┴────────────┐
          │  路径 1: SDK 外部采集 │    │ 路径 2: Wiki Agent  │
          │  (外部 Agent 进程)   │    │ (嵌入同一 FastAPI)  │
          └─────────────────────┘    └─────────────────────┘

          ┌─────────────────────┐    ┌─────────────────────┐
          │  路径 3: Sandbox    │    │ 路径 4: 手动 API    │
          │  (平台运行 Agent)   │    │ (用户提交轨迹)      │
          └─────────────────────┘    └─────────────────────┘
```

---

## 二、四条数据采集路径

### 路径 1: SDK 外部采集（HTTP 模式）

**适用场景**：Agent 运行在独立进程中，通过 HTTP 推送轨迹数据。

**触发条件**：`EVAL_INPROCESS=false` 或 API 地址不是 localhost。

**代码流程**：

```
Agent 代码
  │
  ├─ collector.start(goal, context)                    # sdk/collector.py:383
  │    ├─ 生成 UUID task_id
  │    ├─ POST /api/v1/tasks/                          # 创建评估任务
  │    └─ record(PLAN, {goal, context})                # 自动记录初始计划
  │
  ├─ collector.record_retrieval(query, results, ms)    # sdk/collector.py:874
  │    └─ record(RETRIEVAL, {...})                     # 追加到内存缓冲
  │
  ├─ collector.record_tool_call(name, input, output)   # sdk/collector.py:650
  │    └─ record(TOOL_CALL, {...})                     # 追加到内存缓冲
  │
  ├─ collector.record_think("分析结果")                 # sdk/collector.py:699
  │    └─ record(THINK, {thought})                     # 追加到内存缓冲
  │
  └─ collector.finish(auto_run=True)                   # sdk/collector.py:448
       ├─ record(THINK, "Run finished")
       ├─ _flush(block=True)                           # 批量上传
       │    └─ POST /api/v1/tasks/{id}/trajectory      # 发送所有缓冲步骤
       ├─ PUT /api/v1/tasks/{id}  status=completed     # 标记任务完成
       └─ POST /api/v1/evaluations/                    # 触发评估
```

**关键代码** (`sdk/collector.py:561-629`)：

```python
def record(self, action_type, action_detail, observation=None, *, dedupe_key=None):
    """核心记录方法 — 所有便捷方法的底层实现。"""
    session = self._session()
    if not session.task_id or not self._enabled:
        return None

    # 去重检查
    if dedupe_key:
        key = f"{action_type}:{dedupe_key}"
        if key in session.seen_events:
            return None
        session.seen_events.add(key)

    # 构建步骤
    with self._buffer_lock:
        session.step_counter += 1
        step = {
            "step_number": session.step_counter,
            "action_type": action_type,
            "action_detail": _short(action_detail),    # 截断到 4000 字符
            "observation": _observation_text(observation),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        session.steps.append(step)

        # 缓冲区满时自动 flush
        if len(session.steps) >= self._batch_size and not self.use_inprocess():
            threading.Thread(target=self._flush_steps, ...).start()

        return step
```

---

### 路径 2: 进程内直写（Wiki Agent 嵌入模式）

**适用场景**：Wiki Agent 运行在评估平台的同一 FastAPI 进程中。

**触发条件**：`EVAL_INPROCESS=true` 且 API 地址是 localhost（默认配置）。

**代码流程**：

```
Wiki Agent (graph.py)
  │
  ├─ hooks.emit_session_start(goal, sid, ctx)          # hooks.py:73
  │    └─ await collector.start_async(goal, ctx)       # sdk/collector.py:422
  │         └─ inprocess_transport.create_task_record() # 直接写 DB
  │              └─ EvaluationService.create_task()     # SQLAlchemy INSERT
  │
  ├─ hooks.emit_retrieval(query, results, ms)           # hooks.py:85
  │    └─ collector.record_retrieval(...)               # 内存缓冲
  │
  ├─ hooks.emit_key_facts(facts)                        # hooks.py:96
  │    └─ collector.record_memory_write(...)            # 内存缓冲
  │
  ├─ hooks.emit_response(sid, response)                 # hooks.py:107
  │    └─ collector.record(EVIDENCE, {...})             # 内存缓冲
  │
  └─ hooks.emit_session_end(sid)                        # hooks.py:121
       └─ await collector.finish_async(auto_run=True)   # sdk/collector.py:488
            └─ inprocess_transport.persist_collector_session()
                 ├─ service.add_trajectory(steps)       # 批量写入轨迹
                 ├─ service.update_task(status=completed)
                 ├─ service.create_evaluation()         # 创建评估记录
                 └─ asyncio.create_task(_run_evaluation_background())
                      └─ service.run_evaluation()       # 后台运行 6 个评估器
```

**关键代码** (`app/collectors/inprocess_transport.py:49-76`)：

```python
async def persist_collector_session(task_id, steps, *, auto_run=False, ...):
    """进程内直写 — 绕过 HTTP，直接写 DB。"""
    async with async_session_factory() as db:
        service = EvaluationService(db)

        # 1. 写入所有轨迹步骤
        await service.add_trajectory(task_id, steps)

        # 2. 标记任务完成
        await service.update_task(task_id, TaskUpdate(status="completed"))

        # 3. 创建评估记录
        if auto_run:
            eval_record = await service.create_evaluation(task_id)

        await db.commit()

    # 4. 后台触发评估
    if auto_run and eval_record:
        asyncio.create_task(_run_evaluation_background(task_id, eval_record.id))
```

**为什么需要进程内直写？**

如果 Wiki Agent 用 HTTP 模式，它会向 `http://127.0.0.1:8000` 发请求，而自己就运行在 `127.0.0.1:8000` 上 —— 这会导致**HTTP 自死锁**（自己请求自己，请求永远无法完成）。进程内直写绕过 HTTP，直接用 SQLAlchemy 写 DB。

---

### 路径 3: Sandbox 自动采集

**适用场景**：评估平台在 Docker 容器中运行 Agent，自动捕获完整轨迹。

**代码流程**：

```
POST /api/v1/evaluations/run
  │
  └─ EvaluationService.run_sandbox_evaluation()         # evaluation_service.py:518
       │
       ├─ 1. 创建评估任务 (DB)
       │     └─ service.create_task(TaskCreate(goal=...))
       │
       ├─ 2. 运行 Agent (Docker 沙箱)
       │     └─ AgentRunner().run(goal, ...)            # runner.py:73
       │          │
       │          ├─ recorder = TrajectoryRecorder()    # 创建轨迹记录器
       │          ├─ tool_proxy = ToolProxy(recorder=recorder)  # 工具代理注入 recorder
       │          ├─ graph = create_agent_graph(recorder=recorder)
       │          │
       │          ├─ graph.ainvoke(state)               # Agent 执行
       │          │    ├─ recorder.record_plan(plan)    # 自动记录计划
       │          │    ├─ recorder.record_think(...)    # 自动记录思考
       │          │    ├─ recorder.record_tool_call(...) # 自动记录工具调用
       │          │    └─ recorder.record_node_execute(...) # 自动记录节点
       │          │
       │          └─ return AgentRunResult(trajectory=recorder.get_trajectory())
       │
       ├─ 3. 持久化轨迹
       │     └─ service.add_trajectory(task_id, trajectory)
       │
       ├─ 4. 运行评估
       │     └─ evaluate_parallel(trajectory)            # 6 个评估器并行
       │
       └─ 5. 保存结果
             └─ _persist_evaluation_results(scores)
```

**关键代码** (`app/agent_runtime/runner.py:167-184`)：

```python
# 创建 TrajectoryRecorder，注入到所有组件
recorder = TrajectoryRecorder()
tool_proxy = ToolProxy(container=..., allowed_tools=..., recorder=recorder)
llm = create_llm(provider=provider, model=model, ...)

# 构建 Agent 图，recorder 在每个节点被调用
graph = create_agent_graph(llm=llm, tool_proxy=tool_proxy, recorder=recorder)

# 执行 Agent
final_state = await asyncio.wait_for(graph.ainvoke(initial_state), timeout=agent_timeout)

# 获取完整轨迹
trajectory = recorder.get_trajectory()
```

**为什么 Sandbox 能自动采集？**

因为 `TrajectoryRecorder` 被注入到了 Agent 的每个组件中：
- `ToolProxy` 在每次工具调用时调用 `recorder.record_tool_call()`
- `create_agent_graph` 在每个节点执行时调用 `recorder.record_node_execute()`
- Agent 的 planner 在生成计划时调用 `recorder.record_plan()`

---

### 路径 4: 手动 API 提交

**适用场景**：用户通过 REST API 手动提交轨迹数据。

```bash
# 1. 创建任务
curl -X POST /api/v1/tasks/ -d '{"goal": "实现登录功能"}'

# 2. 提交轨迹步骤
curl -X POST /api/v1/tasks/{task_id}/trajectory -d '[
  {"step_number": 1, "action_type": "plan", "action_detail": {...}},
  {"step_number": 2, "action_type": "tool_call", "action_detail": {...}},
  ...
]'

# 3. 触发评估
curl -X POST /api/v1/evaluations/ -d '{"task_id": "..."}'
```

**关键代码** (`app/api/v1/endpoints/tasks.py:116-141`)：

```python
@router.post("/{task_id}/trajectory", status_code=201)
async def add_trajectory(task_id: str, steps: List[TrajectoryStep], ...):
    steps_data = [step.model_dump() for step in steps]
    await service.add_trajectory(task_id, steps_data, workspace_id=...)
    return {"message": f"Added {len(steps_data)} trajectory steps"}
```

---

## 三、14 种轨迹数据类型详解

### 3.1 规划类

| ActionType | 记录方法 | 数据格式 | 示例 |
|-----------|---------|---------|------|
| `PLAN` | `start()` 自动记录 | `{goal, context}` | `{"goal": "实现登录", "context": {"key_facts": [...]}}` |
| `PLAN_UPDATE` | `record_plan_update()` | `{milestone_status, next_action, reason, remaining_steps}` | `{"milestone_status": {"step1": "done"}, "next_action": "实现注册"}` |
| `REPLAN` | `record_replan()` | `{reason, new_plan, trigger}` | `{"reason": "JWT 库不兼容", "new_plan": "升级到 v2.0"}` |

### 3.2 工具类

| ActionType | 记录方法 | 数据格式 | 示例 |
|-----------|---------|---------|------|
| `TOOL_CALL` | `record_tool_call()` | `{tool_name, input, duration_ms}` + observation=output | `{"tool_name": "sandbox", "input": {"code": "print(1)"}}` |
| `TOOL_RESULT` | `record_tool_result()` | `{tool_name, success, error_type, duration_ms}` + observation=output | `{"tool_name": "sandbox", "success": true}` |
| `TOOL_DECISION` | `record(TOOL_DECISION, ...)` | `{node_name, tool_name, input}` | `{"node_name": "decide", "tool_name": "search"}` |

### 3.3 记忆类

| ActionType | 记录方法 | 数据格式 | 示例 |
|-----------|---------|---------|------|
| `MEMORY_WRITE` | `record_memory_write()` | `{key, value, source, memory_type}` | `{"key": "key_facts", "value": ["用户偏好 Python"]}` |
| `MEMORY_READ` | `record_memory_read()` | `{key, value, context, hit}` | `{"key": "user_pref", "hit": true}` |

### 3.4 状态类

| ActionType | 记录方法 | 数据格式 | 示例 |
|-----------|---------|---------|------|
| `STATE_CHANGE` | `record_state_change()` | `{node_name, trigger, diff}` | `{"diff": {"messages": {"type": "list", "old_len": 5, "new_len": 6}}}` |
| `NODE_EXECUTE` | `record_node_execute()` | `{node_name, input, output}` | `{"node_name": "search", "input": {"query": "..."}}` |

### 3.5 推理类

| ActionType | 记录方法 | 数据格式 | 示例 |
|-----------|---------|---------|------|
| `THINK` | `record_think()` | `{thought}` | `{"thought": "分析 JWT 过期问题"}` |

### 3.6 异常类

| ActionType | 记录方法 | 数据格式 | 示例 |
|-----------|---------|---------|------|
| `FAILURE` | `record_failure()` | `{error_type, error_message, context, recoverable, node_name, stack_trace}` | `{"error_type": "TimeoutError", "recoverable": true}` |

### 3.7 检索类

| ActionType | 记录方法 | 数据格式 | 示例 |
|-----------|---------|---------|------|
| `RETRIEVAL` | `record_retrieval()` | `{query, source, result_count, duration_ms, retrieved_docs}` | `{"query": "JWT 认证", "retrieved_docs": [{"title": "...", "snippet": "..."}]}` |
| `EVIDENCE` | `record_evidence()` | `{evidence_type, context, sources, final_prompt_messages}` | `{"sources": {"retrieved_docs_count": 3, "tool_results_count": 1}}` |

---

## 四、核心代码逐行解析

### 4.1 SDK Collector — 数据采集核心

**文件**：`sdk/collector.py`

#### 单例创建

```python
# line 258-323
class TrajectoryCollector:
    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls):
        # 双重检查锁定 — 线程安全的单例
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        with self._instance_lock:
            if self._initialized:
                return
            self._initialized = True
            self._buffer_lock = threading.Lock()   # 保护 steps 缓冲区
            self._flush_lock = threading.Lock()    # 防止并发 flush
            self._enabled = _env_bool("EVAL_ENABLED", True)
            self._api_base = _env_str("EVAL_API_BASE_URL", "http://127.0.0.1:8000")
            self._batch_size = _env_int("EVAL_BATCH_SIZE", 10)
            self._inprocess = _env_bool("EVAL_INPROCESS", True)
```

**为什么用单例？**
- 所有请求共享同一个 HTTP 客户端（连接复用）
- 全局统一的配置管理
- 通过 ContextVar 实现会话隔离

#### 会话隔离（ContextVar）

```python
# line 232-240
@dataclass
class _CollectorSession:
    task_id: Optional[str] = None          # 当前任务 ID
    step_counter: int = 0                   # 步骤计数器
    steps: List[Dict[str, Any]] = field(default_factory=list)  # 缓冲区
    seen_events: _BoundedSet = ...          # 去重集合

# line 247 — 每个 async 任务有独立的 session
_collector_session: ContextVar[Optional[_CollectorSession]] = ContextVar(...)
```

**为什么用 ContextVar？**
- 并发的 Wiki 对话会同时调用 collector
- 每个对话需要独立的 task_id 和 steps 缓冲区
- ContextVar 在 asyncio 中自动隔离，无需手动传递

#### 进程内模式判断

```python
# line 347-355
def use_inprocess(self) -> bool:
    """判断是否使用进程内直写（避免 HTTP 自死锁）。"""
    if not self._inprocess or not self._enabled:
        return False
    base = self._api_base.rstrip("/")
    return base in ("http://127.0.0.1:8000", "http://localhost:8000")
```

**为什么需要这个判断？**
- Wiki Agent 运行在 `127.0.0.1:8000`（FastAPI）
- 如果用 HTTP 模式，会向自己发请求 → 死锁
- 进程内模式直接用 SQLAlchemy 写 DB，绕过 HTTP

---

### 4.2 Hooks 层 — Wiki Agent 与 SDK 的桥梁

**文件**：`app/wiki_agent/hooks.py`

```python
# line 15-27 — SDK 导入 + 降级
try:
    from sdk.collector import ActionType, get_collector
    _HAS_SDK = True
except ImportError:
    _HAS_SDK = False
    def _get_collector(): return None  # SDK 不可用时返回 None

# line 73-83 — 会话开始
async def emit_session_start(goal, session_id, context):
    collector = _get_collector()
    if collector is None or not collector.enabled:
        return                              # SDK 不可用 → 静默跳过
    try:
        await collector.start_async(goal, context)  # 创建评估任务
    except Exception as e:
        logger.warning("emit_session_start error: %s", e)  # 失败不阻塞

# line 85-93 — 检索记录
async def emit_retrieval(query, results, duration_ms):
    collector = _get_collector()
    if collector is None or not collector.enabled:
        return
    try:
        collector.record_retrieval(query, results, duration_ms=duration_ms)
    except Exception as e:
        logger.warning("emit_retrieval error: %s", e)

# line 121-131 — 会话结束
async def emit_session_end(session_id):
    collector = _get_collector()
    if collector is None or not collector.enabled:
        return
    try:
        await collector.finish_async(auto_run=True)  # flush + 触发评估
    except Exception as e:
        logger.warning("emit_session_end error: %s", e)
```

**为什么 hooks.py 要存在？**
1. **解耦**：graph.py 不直接依赖 SDK，只依赖 hooks.py
2. **降级**：SDK 不可用时所有操作静默跳过
3. **统一错误处理**：所有异常被捕获并记录日志，不阻塞业务

---

### 4.3 Graph.py — 业务代码中的调用点

**文件**：`app/wiki_agent/agent/graph.py`

```python
# line 30 — 导入 hooks
from app.wiki_agent.hooks import (
    emit_key_facts, emit_retrieval, emit_response,
    emit_session_end, emit_session_start
)

# line 595-654 — run_chat_stream()
async def run_chat_stream(user_message, chat_history, session_id=None):
    # ... 初始化 ...

    # ★ 调用点 1：会话开始
    await emit_session_start(user_message, session_id or "",
        {"thread_id": thread_id, "mode": "stream"})

    # ... 执行 LangGraph ...

    # ★ 调用点 2：在 search 节点内
    # line 364: 检索完成后
    await emit_retrieval(user_message, ctx.wiki_results, duration_ms)

    # line 399: 事实提取后
    await emit_key_facts([f.get("content", "") for f in facts])

    # ★ 调用点 3：在 respond 节点内
    # line 454: 回复生成后
    await emit_response(session_id, collected)

    # ★ 调用点 4：会话结束（finally 块）
    finally:
        await emit_session_end(session_id or "")  # 确保总能执行
```

**为什么调用点在这些位置？**

| 调用点 | 位置 | 原因 |
|--------|------|------|
| `emit_session_start` | 对话开始时 | 创建评估任务，开始缓冲 |
| `emit_retrieval` | 检索完成后 | 记录检索查询和结果，供 RetrievalEvaluator 消费 |
| `emit_key_facts` | 事实提取后 | 记录记忆写入，供 MemoryEvaluator 消费 |
| `emit_response` | 回复生成后 | 记录最终回复，供 RetrievalEvaluator 做幻觉检测 |
| `emit_session_end` | finally 块 | 确保 flush 轨迹，即使客户端断开也能触发评估 |

---

### 4.4 TrajectoryRecorder — Sandbox 自动采集

**文件**：`app/agent_runtime/trajectory_recorder.py`

```python
# line 38-40
class TrajectoryRecorder:
    def __init__(self):
        self._steps = []
        self._step_counter = 0

    # line 66-94 — 工具调用（一次记录两个步骤）
    def record_tool_call(self, tool_name, tool_input, tool_output, success=True, duration_ms=None):
        # 步骤 1: TOOL_CALL
        self._record(ActionType.TOOL_CALL,
            {"tool_name": tool_name, "input": self._truncate(tool_input)},
            observation=tool_output[:3000])
        # 步骤 2: TOOL_RESULT
        self._record(ActionType.TOOL_RESULT,
            {"tool_name": tool_name, "success": success, "duration_ms": duration_ms})

    # line 51-64 — 思考记录（含 LLM 原始数据）
    def record_think(self, thought, llm_trace=None):
        detail = {"thought": thought}
        self._record(ActionType.THINK, detail, llm_trace=llm_trace)

    # line 154-183 — 核心记录方法
    def _record(self, action_type, action_detail, observation=None, llm_trace=None):
        self._step_counter += 1
        if llm_trace:
            action_detail["_llm_trace"] = {           # 注入 LLM 原始数据
                "prompt": llm_trace.get("prompt", "")[:10000],
                "response": llm_trace.get("response", "")[:10000],
                "model": llm_trace.get("model", "unknown"),
                "latency_ms": llm_trace.get("latency_ms", 0),
            }
        step = {
            "step_number": self._step_counter,
            "action_type": action_type,
            "action_detail": action_detail,
            "observation": observation,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._steps.append(step)
```

**为什么 TrajectoryRecorder 能自动采集？**

因为它被注入到了 Agent 的每个组件：

```python
# runner.py:167-173
recorder = TrajectoryRecorder()
tool_proxy = ToolProxy(container=..., recorder=recorder)  # 工具代理持有 recorder
graph = create_agent_graph(recorder=recorder)              # 图节点持有 recorder
```

- `ToolProxy` 每次执行工具时调用 `recorder.record_tool_call()`
- Agent 图的每个节点执行时调用 `recorder.record_node_execute()`
- Planner 生成计划时调用 `recorder.record_plan()`

---

## 五、数据消费：6 个评估器

### 5.1 评估器如何提取数据

**文件**：`app/evaluators/base.py`

每个评估器通过 `_extract_*()` 方法从轨迹中提取相关的步骤：

```python
# line 187 — 提取计划步骤
def _extract_plans(self, trajectory):
    return [s for s in trajectory if s.get("action_type") == "plan"]

# line 207 — 提取工具调用
def _extract_tool_calls(self, trajectory):
    return [s for s in trajectory if s.get("action_type") == "tool_call"]

# line 261 — 提取记忆事件
def _extract_memory_events(self, trajectory):
    return [s for s in trajectory
            if s.get("action_type") in ("memory_write", "memory_read")]

# line 306 — 提取检索事件
def _extract_retrievals(self, trajectory):
    return [s for s in trajectory if s.get("action_type") == "retrieval"]
```

### 5.2 评估器消费的 ActionType 映射

```
轨迹数据 (14 种 ActionType)
    │
    ├─ PLAN, PLAN_UPDATE ──────→ PlanningEvaluator
    │    └─ 评估：覆盖度、排序、粒度、完整性
    │
    ├─ 所有非 PLAN 步骤 ───────→ TacticalEvaluator
    │    └─ 评估：相关性、效率、正确性
    │
    ├─ TOOL_CALL, TOOL_RESULT ─→ ToolUseEvaluator
    │    └─ 评估：选择质量、参数准确、结果利用
    │
    ├─ MEMORY_WRITE, MEMORY_READ → MemoryEvaluator
    │    └─ 评估：保持度、相关性、一致性
    │
    ├─ REPLAN, FAILURE ────────→ ReplanEvaluator
    │    └─ 评估：触发时机、适应质量、学习能力
    │
    └─ RETRIEVAL, EVIDENCE ────→ RetrievalEvaluator
         └─ 评估：相关性、证据准确、覆盖度、幻觉检测
```

### 5.3 评估流程

```python
# app/services/evaluation_service.py:339-461
async def run_evaluation(self, task_id, ...):
    # 1. 从 DB 加载轨迹
    trajectory = await self._get_trajectory(task_id)

    # 2. 6 个评估器并行执行
    results = await evaluate_parallel(goal, trajectory, context)

    # 3. 保存结果
    await self._persist_evaluation_results(evaluation_id, results)
```

---

## 六、数据库表结构

### 6.1 核心表

```sql
-- 评估任务
CREATE TABLE agent_tasks (
    id TEXT PRIMARY KEY,
    goal TEXT NOT NULL,                    -- 任务目标
    context JSON,                          -- 任务上下文
    status TEXT DEFAULT 'pending',         -- pending/running/completed/failed
    workspace_id TEXT,
    created_at TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

-- 轨迹步骤
CREATE TABLE agent_trajectories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES agent_tasks(id),
    step_number INTEGER NOT NULL,          -- 步骤序号
    action_type TEXT NOT NULL,             -- 14 种 ActionType 之一
    action_detail JSON NOT NULL,           -- 动作详情（结构化数据）
    observation TEXT,                      -- 观察结果（文本）
    timestamp TIMESTAMP NOT NULL           -- UTC 时间戳
);

-- 评估结果
CREATE TABLE evaluations (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES agent_tasks(id),
    status TEXT DEFAULT 'pending',         -- pending/in_progress/completed/failed

    -- 6 维评分
    planning_score FLOAT,
    tactical_score FLOAT,
    tool_use_score FLOAT,
    memory_score FLOAT,
    replan_score FLOAT,
    retrieval_score FLOAT,
    overall_score FLOAT,                   -- 加权综合分

    -- 6 维反馈（含 Judge 原始数据）
    planning_feedback JSON,
    tactical_feedback JSON,
    tool_use_feedback JSON,
    memory_feedback JSON,
    replan_feedback JSON,
    retrieval_feedback JSON,

    -- 元数据
    prompt_version TEXT,
    model_name TEXT,
    model_provider TEXT,
    workspace_id TEXT,
    created_at TIMESTAMP,
    completed_at TIMESTAMP
);
```

### 6.2 action_detail JSON 结构示例

```json
// PLAN 类型
{
    "goal": "实现用户登录功能",
    "context": {"key_facts": ["项目使用 JWT", "数据库是 PostgreSQL"]}
}

// TOOL_CALL 类型
{
    "tool_name": "sandbox",
    "input": {"code": "import jwt; print(jwt.__version__)"},
    "duration_ms": 1234.5
}

// RETRIEVAL 类型
{
    "query": "JWT 认证最佳实践",
    "source": "hybrid_search",
    "result_count": 5,
    "duration_ms": 156.7,
    "retrieved_docs": [
        {"title": "JWT 认证指南", "path": "auth/jwt-guide.md", "snippet": "...", "score": 0.92}
    ]
}

// MEMORY_WRITE 类型
{
    "key": "key_facts",
    "value": ["用户偏好 Python", "项目使用 asyncio"],
    "source": "llm_extraction",
    "memory_type": "fact"
}
```

---

## 七、为什么能获取到数据

### 7.1 根本原因：显式埋点 + 框架注入

评估平台能获取数据的**根本原因**是 Agent 代码中**显式调用**了 `record_*()` 方法。

这不是"零侵入"的自动采集，而是**有意识的数据暴露**：

| 采集方式 | 机制 | 侵入性 |
|---------|------|--------|
| SDK 外部采集 | Agent 代码显式调用 `collector.record_*()` | 中（需改业务代码） |
| Wiki Agent hooks | graph.py 显式调用 `emit_*()` | 中（6 个调用点） |
| Sandbox 自动采集 | `TrajectoryRecorder` 注入到 Agent 组件 | 低（框架层注入） |

### 7.2 SDK 采集的工作原理

```
Agent 代码
    │
    ├─ "我要记录这个操作" → 调用 collector.record_retrieval(...)
    │                              │
    │                              ▼
    │                    构建 step dict
    │                    {step_number, action_type, action_detail, observation, timestamp}
    │                              │
    │                              ▼
    │                    追加到内存缓冲区 (session.steps)
    │                              │
    │                    缓冲区满或 finish() 时
    │                              ▼
    │                    批量 POST 到评估平台 API
    │                              │
    │                              ▼
    │                    EvaluationService.add_trajectory()
    │                    写入 agent_trajectories 表
    │                              │
    │                              ▼
    │                    run_evaluation()
    │                    6 个评估器读取轨迹，LLM 评分
    │                              │
    │                              ▼
    │                    写入 evaluations 表
    │                    前端展示 6 维雷达图
```

### 7.3 关键设计决策

| 决策 | 原因 |
|------|------|
| 用内存缓冲而非实时上传 | 减少 HTTP 请求次数，提升性能 |
| 用 ContextVar 而非全局变量 | 支持并发请求的会话隔离 |
| 用进程内直写而非 HTTP | 避免嵌入模式下的自死锁 |
| 用去重集合而非简单追加 | 防止重试导致的重复记录 |
| 用 LLM-as-Judge 而非规则 | 评估需要理解语义，规则无法覆盖 |

### 7.4 数据完整性保障

| 保障机制 | 说明 |
|---------|------|
| 失败回退缓冲 | flush 失败时步骤回退到本地缓冲，下次 flush 重试 |
| 指数退避重试 | HTTP 请求最多重试 3 次（0.5s → 1s → 2s） |
| finally 块保证 | `emit_session_end` 在 finally 块中，确保总能执行 |
| 去重集合 | `_BoundedSet`（LRU，5000 条）防止重复记录 |
| 离线模式 | `EVAL_ENABLED=false` 时静默跳过，不阻塞 Agent |
