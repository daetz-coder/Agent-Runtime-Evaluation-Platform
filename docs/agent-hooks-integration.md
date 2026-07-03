# Agent Hooks 集成指南 — 任意 Agent 项目接入评估平台

> **入口**: [README.md](../README.md) · **SDK 集成**: [adapters.md](adapters.md) · **API**: [api.md](api.md)

---

## 概述

`agent-hooks` 是一个轻量级 SDK，让**任意 Agent 项目**（不限框架）以最小侵入接入 Agent Runtime Evaluation Platform。

```
你的 Agent 项目                    评估平台
     │                                │
     │  await emit.retrieval(...)     │
     │  await emit.response(...)      │
     │──────────────────────────────▶ │  register(EvalHooks())
     │                                │  → 自动采集轨迹
     │                                │  → 6 维评估
     │                                │  → 生成报告
```

### 与 SDK Adapter 的区别

| | agent-hooks | sdk/ (LangGraph Adapter) |
|---|---|---|
| **适用框架** | 任意（LangGraph、AutoGen、CrewAI、自研等） | LangGraph / LangChain |
| **接入方式** | 手动在关键点调用 `emit.*()` | 一行 `instrument_langgraph()` 自动采集 |
| **采集粒度** | Agent 自定义的业务层事件 | 框架内部的节点/状态/工具/LLM 自动采集 |
| **代码修改** | 需要在 5-8 个关键点添加调用 | 不修改代码，只替换一行 |
| **灵活性** | 完全自定义采集内容 | 固定采集框架暴露的信息 |

**推荐策略**：
- **LangGraph 项目** → 优先用 `sdk/` 自动采集，可选补充 `agent-hooks` 业务事件
- **非 LangGraph 项目** → 用 `agent-hooks` 手动接入
- **需要自定义采集** → 用 `agent-hooks` 精确控制

---

## 什么是关键节点

Agent 的执行是一个流程，**关键节点**是这个流程中对评估有意义的事件发生点：

```
用户输入
  │
  ▼
┌─────────────┐
│ ① 会话开始    │ ← emit.session_start()    评估平台创建任务
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ ② 检索       │ ← emit.retrieval()        评估"检索质量"维度
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ ③ LLM 推理   │ ← emit.llm_call()         评估"规划质量"+"战术决策"维度
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ ④ 工具调用    │ ← emit.tool_call()        评估"工具使用"维度
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ ⑤ 记忆写入    │ ← emit.key_facts()        评估"记忆保持"维度
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ ⑥ 生成回复    │ ← emit.response()         评估"战术决策"维度
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ ⑦ 会话结束    │ ← emit.session_end()      触发评估、生成报告
└─────────────┘
```

### 关键节点与评估维度的映射

| 关键节点 | emit 事件 | 评估平台拿到什么 | 评估什么维度 |
|----------|-----------|-----------------|-------------|
| 会话开始 | `session_start` | 任务目标、上下文 | — （创建任务） |
| 检索完成 | `retrieval` | 查询词、检索结果、耗时 | **检索质量** |
| LLM 调用 | `llm_call` | 输入消息、输出回复 | **规划质量** + **战术决策** |
| 工具调用 | `tool_call` | 工具名、参数、返回值 | **工具使用** |
| 记忆写入 | `key_facts` | 提取的事实 | **记忆保持** |
| 生成回复 | `response` | 最终回复内容 | **战术决策** |
| 错误发生 | `error` | 异常信息 | **重规划** |
| 会话结束 | `session_end` | — | 触发评估、生成报告 |

---

## 你需要提供什么

### 你的 Agent 项目需要做的（你负责）

只需要 **2 件事**：

1. `pip install agent-hooks`
2. 在关键位置加 `await emit.xxx()`（每个 1 行代码）

```python
from agent_hooks import emit

async def your_agent(goal: str):
    session_id = generate_session_id()

    # 你调了 → 评估对应维度
    # 没调  → 该维度标记 N/A，不影响其他维度
    await emit.session_start(goal, session_id, {"agent": "your-agent"})

    results = await your_search(query)
    await emit.retrieval(query, results, duration_ms)      # → 评估"检索质量"

    response = await your_llm.call(messages)
    await emit.llm_call(model, messages, response)          # → 评估"规划+战术"

    for tool_call in response.tool_calls:
        result = await your_tool.run(tool_call)
        await emit.tool_call(tool_call.name, tool_call.args, result)  # → 评估"工具使用"

    await emit.response(session_id, final_answer)
    await emit.session_end(session_id)                      # 必须调用，触发评估
```

### 评估平台已经提供的（不需要你写）

| 组件 | 说明 | 谁提供 |
|------|------|--------|
| `AgentHooks` 接口 | 标准化的事件协议 | `agent-hooks` SDK |
| `NoOpHooks` 默认实现 | 独立运行时的空操作 | `agent-hooks` SDK |
| `Emitter` 事件发射器 | 注册 + 触发 + 异常隔离 | `agent-hooks` SDK |
| `EvalHooks` 实现 | 把事件转为评估数据 | 评估平台 |
| `TrajectoryCollector` | 轨迹存储和上报 | 评估平台 |
| 6 个评估器 | LLM-as-Judge 评分 | 评估平台 |
| 评估报告 | 可视化展示 | 评估平台前端 |

### 完整数据流

```
你的 Agent 项目                    agent-hooks SDK              评估平台
     │                                │                           │
     │  emit.retrieval()              │                           │
     │──────────────────────────────▶ │                           │
     │                                │  _hooks.on_retrieval()    │
     │                                │──────────────────────────▶│
     │                                │                           │  EvalHooks 实现
     │                                │                           │  → TrajectoryCollector
     │                                │                           │  → 存储到数据库
     │                                │                           │
     │  emit.session_end()            │                           │
     │──────────────────────────────▶ │                           │
     │                                │  _hooks.on_session_end()  │
     │                                │──────────────────────────▶│
     │                                │                           │  触发 6 个评估器
     │                                │                           │  → 生成评估报告
     │                                │                           │  → 前端展示
```

---

## 快速接入（5 分钟）

### 第 1 步：安装 agent-hooks

```bash
pip install -e /path/to/agent-hooks/
```

### 第 2 步：在 Agent 代码中添加 emit 调用

在你的 Agent 代码中，找到以下关键位置并添加对应的 emit 调用：

```python
from agent_hooks import emit

class MyAgent:
    async def run(self, goal: str, session_id: str):
        """Agent 主流程"""

        # ① 会话开始 — 必须
        await emit.session_start(goal, session_id, {
            "agent": "my-agent",
            "version": "1.0",
        })

        try:
            # ② 检索 — 如果是 RAG Agent
            results = await self.retrieve(query)
            await emit.retrieval(query, results, duration_ms=150.0)

            # ③ LLM 调用 — 如果需要记录
            response = await self.llm.ainvoke(messages)
            await emit.llm_call(
                model="gpt-4",
                messages=[m.dict() for m in messages],
                response=response.content,
            )

            # ④ 工具调用 — 如果使用工具
            for tool_call in response.tool_calls:
                result = await self.execute_tool(tool_call)
                await emit.tool_call(
                    tool_name=tool_call["name"],
                    args=tool_call["args"],
                    result=result,
                    duration_ms=50.0,
                )

            # ⑤ 记忆提取 — 如果有记忆系统
            facts = self.extract_facts(response)
            if facts:
                await emit.key_facts(facts, scope="session")

            # ⑥ 生成回复
            final_answer = self.generate_answer(response)
            await emit.response(session_id, final_answer)

        except Exception as e:
            # ⑦ 错误记录
            await emit.error(session_id, e)
            raise

        finally:
            # ⑧ 会话结束 — 必须
            await emit.session_end(session_id)
```

### 第 3 步：正常运行

```bash
python my_agent.py
```

独立运行时，所有 emit 调用为空操作，零开销。

### 第 4 步：接入评估平台

评估平台侧实现 hooks 并注册：

```python
# 在评估平台中
from agent_hooks import AgentHooks, register

class EvalHooks(AgentHooks):
    """评估平台 hooks 实现"""

    async def on_session_start(self, goal, session_id, context):
        """创建评估任务"""
        from sdk import get_collector
        self.collector = get_collector()
        self.task_id = self.collector.start(goal, context)

    async def on_retrieval(self, query, results, duration_ms):
        """记录检索轨迹"""
        self.collector.record_retrieval(
            query=query,
            retrieved_docs=[
                {"title": r.get("title"), "path": r.get("path"), "snippet": r.get("snippet")}
                for r in results
            ],
            source="hybrid_search",
            duration_ms=duration_ms,
        )

    async def on_llm_call(self, model, messages, response, usage):
        """记录 LLM 调用"""
        self.collector.record(
            "tool_call",
            {
                "tool_name": "llm",
                "model": model,
                "input": messages[-1] if messages else {},
                "output": response[:500],
            },
        )

    async def on_key_facts(self, facts, scope):
        """记录记忆操作"""
        for fact in facts:
            self.collector.record_memory_write(
                key=fact, value=fact, source="llm_extraction"
            )

    async def on_response(self, session_id, response):
        """记录回复"""
        self.collector.record(
            "think", {"thought": response[:200]}
        )

    async def on_error(self, session_id, error):
        """记录错误"""
        self.collector.record(
            "failure", {"error": str(error)}
        )

    async def on_session_end(self, session_id):
        """结束评估"""
        self.collector.finish(auto_run=True)


# 评估平台启动时注册
register(EvalHooks())
```

---

## 各框架接入示例

### LangGraph Agent

```python
from agent_hooks import emit
from langgraph.graph import StateGraph, END

async def search_node(state, config):
    query = state["query"]
    results = await hybrid_search(query)
    await emit.retrieval(query, results, duration_ms=100.0)
    return {"results": results}

async def respond_node(state, config):
    response = await llm.ainvoke(state["messages"])
    await emit.llm_call(model, messages, response.content)
    return {"answer": response.content}

# ... 构建 graph ...
```

### AutoGen Agent

```python
from agent_hooks import emit

async def run_autogen(task: str, session_id: str):
    await emit.session_start(task, session_id, {"framework": "autogen"})

    # AutoGen 对话
    result = await agent.initiate_chat(task)

    await emit.response(session_id, result.summary)
    await emit.session_end(session_id)
```

### CrewAI Agent

```python
from agent_hooks import emit

async def run_crew(goal: str, session_id: str):
    await emit.session_start(goal, session_id, {"framework": "crewai"})

    crew = Crew(agents=[...], tasks=[...])
    result = crew.kickoff()

    await emit.response(session_id, str(result))
    await emit.session_end(session_id)
```

### 自研 Agent

```python
from agent_hooks import emit

async def my_agent_loop(goal: str, session_id: str):
    await emit.session_start(goal, session_id, {"framework": "custom"})

    context = []
    for step in range(max_steps):
        # 思考
        thought = await think(goal, context)
        await emit.llm_call("my-llm", context, thought)

        # 行动
        action = decide_action(thought)
        if action.type == "search":
            results = await search(action.query)
            await emit.retrieval(action.query, results, action.duration)
        elif action.type == "tool":
            result = await use_tool(action.tool, action.args)
            await emit.tool_call(action.tool, action.args, result)

        context.append(thought)

    await emit.response(session_id, context[-1])
    await emit.session_end(session_id)
```

---

## 事件与评估维度的映射

| emit 事件 | 评估维度 | 评估器 |
|-----------|----------|--------|
| `session_start` | — | 创建评估任务 |
| `llm_call` | 规划质量、战术决策 | `planning_evaluator`, `tactical_evaluator` |
| `tool_call` | 工具使用 | `tool_use_evaluator` |
| `retrieval` | 检索质量 | `retrieval_evaluator` |
| `key_facts` | 记忆保持 | `memory_evaluator` |
| `response` | 战术决策 | `tactical_evaluator` |
| `error` | 重规划 | `replan_evaluator` |
| `session_end` | — | 结束评估，生成报告 |

---

## 评估平台配置

### 启动评估平台

```bash
# 终端 1: 后端
cd D:\Agent Runtime Evaluation Platform
python -m app.main

# 终端 2: 前端
cd frontend && npm run dev
```

### 注册 hooks

在评估平台的启动入口中注册：

```python
# app/main.py 或独立启动脚本
from agent_hooks import register

# 只在评估模式下注册
if os.environ.get("EVAL_ENABLED", "true").lower() == "true":
    from your_eval_hooks import EvalHooks
    register(EvalHooks())
```

### 查看评估结果

1. 运行你的 Agent：`python my_agent.py`
2. 访问 http://localhost:3000
3. 在"评估任务"中查看自动生成的评估报告
4. 6 维评分：规划、战术、工具使用、记忆、重规划、检索

---

## 最佳实践

### 1. 会话生命周期必须完整

```python
# ✅ 正确：session_start 和 session_end 成对出现
await emit.session_start(goal, session_id, ctx)
# ... Agent 逻辑 ...
await emit.session_end(session_id)

# ❌ 错误：只有 start 没有 end（评估任务永远不会结束）
await emit.session_start(goal, session_id, ctx)
# ... 忘记调用 session_end ...
```

### 2. 异常时也要调用 session_end

```python
# ✅ 正确：用 try/finally 保证
await emit.session_start(goal, session_id, ctx)
try:
    # ... Agent 逻辑 ...
    await emit.response(session_id, answer)
finally:
    await emit.session_end(session_id)
```

### 3. 只调用你有的事件

```python
# ✅ 正确：RAG Agent 只调用检索相关事件
await emit.session_start(...)
await emit.retrieval(query, results, duration_ms)
await emit.response(session_id, answer)
await emit.session_end(...)

# ✅ 也正确：纯聊天 Agent 不调用 retrieval
await emit.session_start(...)
await emit.llm_call(model, messages, response)
await emit.response(session_id, answer)
await emit.session_end(...)
```

### 4. context 字段传递元数据

```python
# 可以在 context 中传递任意元数据，评估平台会记录
await emit.session_start(goal, session_id, {
    "agent": "my-agent",
    "version": "2.0",
    "user_id": "user-123",
    "task_type": "qa",
    "model": "gpt-4",
})
```

---

## 常见问题

### Q: agent-hooks 会影响 Agent 性能吗？

A: **不会。** 独立运行时所有 emit 调用是空操作（`pass`），开销为零。接入评估平台时，hooks 调用是异步的，不阻塞 Agent 主流程。

### Q: 可以只接入部分事件吗？

A: **可以。** 只调用你需要的事件。评估平台会根据可用数据自动适配评估维度。缺少某些事件时，对应维度标记为 N/A。

### Q: 多个 Agent 项目可以同时接入吗？

A: **可以。** 每个 Agent 的 `session_id` 唯一标识一次运行，评估平台按 session 分别评估。

### Q: 评估平台没运行时 emit 会报错吗？

A: **不会。** hooks 实现中的异常被 try/except 捕获并记录日志，不影响 Agent 运行。

### Q: 可以和 sdk/ (LangGraph Adapter) 一起用吗？

A: **可以。** `sdk/` 自动采集框架内部细节，`agent-hooks` 记录业务层语义事件，两者互补。

---

## 相关文档

| 文档 | 内容 |
|------|------|
| [agent-hooks API](../agent-hooks/README.md) | SDK API 参考、高级用法 |
| [SDK 集成指南](adapters.md) | LangGraph Adapter / LLM Proxy / Callback 三种方式 |
| [评估体系](../README.md#评估体系) | 6 维评分、20 项子指标 |
| [API 文档](api.md) | 评估平台 REST API |
| [快速开始](getting_started.md) | 评估平台安装与配置 |
