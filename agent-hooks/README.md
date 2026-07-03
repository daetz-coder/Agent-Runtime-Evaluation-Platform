# agent-hooks

轻量级 Agent 生命周期钩子 SDK — 零依赖、零侵入的评估接入方案。

任何 Agent 项目只需 `pip install agent-hooks` + 在关键节点调用 `await emit.xxx()`，即可接入 Agent Runtime Evaluation Platform 进行全维度质量评估。

---

## 目录

- [安装](#安装)
- [快速开始](#快速开始3-分钟接入)
- [什么是关键节点](#什么是关键节点)
- [你需要提供什么](#你需要提供什么)
- [完整数据流](#完整数据流hooks-与其他概念的关系)
- [API 参考](#api-参考)
- [接入模式](#接入模式)
- [各框架接入示例](#各框架接入示例)
- [与现有 SDK 的关系](#与现有-sdk-的关系)
- [降级方案](#不安装时的降级方案)

---

## 安装

```bash
# 从本地安装（开发模式）
pip install -e agent-hooks/

# 或从 PyPI（发布后）
pip install agent-hooks
```

**零依赖**：只使用 Python 标准库，不引入任何第三方包。

---

## 快速开始（3 分钟接入）

### 第 1 步：安装

```bash
pip install -e agent-hooks/
```

### 第 2 步：在 Agent 代码中添加 emit 调用

```python
from agent_hooks import emit

async def run_agent(goal: str, session_id: str):
    # ① 会话开始
    await emit.session_start(goal, session_id, {"agent": "my-agent"})

    # ② 检索（如果是 RAG Agent）
    results = await search(query)
    await emit.retrieval(query, results, duration_ms=150.0)

    # ③ LLM 调用
    response = await llm.ainvoke(messages)
    await emit.llm_call(model="gpt-4", messages=messages, response=response.content)

    # ④ 工具调用
    result = await tool.run(args)
    await emit.tool_call("search", args, result, duration_ms=50.0)

    # ⑤ 记忆/事实提取
    facts = extract_facts(response)
    await emit.key_facts(facts, scope="session")

    # ⑥ 生成最终回复
    await emit.response(session_id, final_answer)

    # ⑦ 会话结束
    await emit.session_end(session_id)
```

> **只调用你关心的事件**，不需要全部添加。未调用的事件不影响评估。

### 第 3 步：正常运行

```bash
python my_agent.py
```

独立运行时，所有 emit 调用自动降级为空操作，**零开销**。

### 第 4 步（可选）：接入评估平台

评估平台侧实现 hooks 并注册（这部分由评估平台提供，你不需要写）：

```python
# 评估平台已有实现，只需启动时注册
from agent_hooks import register
from eval_platform.hooks_impl import EvalHooks

register(EvalHooks())
```

---

## 什么是关键节点

Agent 的执行是一个流程，**关键节点**是这个流程中对评估有意义的事件发生点。

### 典型 Agent 执行流程

```
用户输入: "帮我搜索 Python 异步编程的最佳实践"
  │
  ▼
┌──────────────────────────────────────────────────────────┐
│ ① 会话开始                                                │
│    emit.session_start("帮我搜索...", "sess-1", ctx)       │
│    → 评估平台创建评估任务                                   │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│ ② 检索                                                   │
│    results = await vector_search("Python 异步编程")        │
│    emit.retrieval(query, results, 120ms)                  │
│    → 评估"检索质量"：结果相关吗？找到了吗？覆盖度够吗？      │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│ ③ LLM 推理                                               │
│    response = await llm.ainvoke(messages)                 │
│    emit.llm_call("gpt-4", messages, response.content)    │
│    → 评估"规划质量"：计划合理吗？                           │
│    → 评估"战术决策"：每步推理正确吗？                        │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│ ④ 工具调用                                                │
│    result = await code_executor.run(code)                 │
│    emit.tool_call("executor", args, result, 300ms)        │
│    → 评估"工具使用"：选对工具了吗？参数对吗？结果用对了吗？   │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│ ⑤ 记忆写入                                                │
│    facts = ["用户偏好 Python", "项目使用 asyncio"]          │
│    emit.key_facts(facts, scope="session")                 │
│    → 评估"记忆保持"：提取了正确信息吗？                      │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│ ⑥ 生成回复                                                │
│    emit.response("sess-1", "Python 异步编程最佳实践...")    │
│    → 评估"战术决策"：回复质量如何？                          │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│ ⑦ 会话结束                                                │
│    emit.session_end("sess-1")                             │
│    → 评估平台触发 6 个评估器并行评分，生成报告               │
└──────────────────────────────────────────────────────────┘
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

接入评估平台时，职责分为两部分：

### 你的 Agent 项目需要做的（你负责）

```python
from agent_hooks import emit  # 1. 安装 agent-hooks，导入 emit

async def your_agent(goal: str):
    session_id = generate_session_id()

    # 2. 在关键节点调用 emit（每个调用 1 行代码）
    await emit.session_start(goal, session_id, {"agent": "your-agent"})

    results = await your_search(query)
    await emit.retrieval(query, results, duration_ms)      # 你调了 → 评估"检索质量"
                                                            # 没调 → 该维度标记 N/A
    response = await your_llm.call(messages)
    await emit.llm_call(model, messages, response)          # 你调了 → 评估"规划+战术"

    for tool_call in response.tool_calls:
        result = await your_tool.run(tool_call)
        await emit.tool_call(tool_call.name, tool_call.args, result)  # 你调了 → 评估"工具使用"

    await emit.response(session_id, final_answer)
    await emit.session_end(session_id)                      # 必须调用，触发评估
```

**总结：你只需要做 2 件事：**
1. `pip install agent-hooks`
2. 在关键位置加 `await emit.xxx()` （每个 1 行代码）

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

### 一句话总结

```
你负责：在关键位置加 emit 调用（报告"我做了什么"）
平台负责：接收事件、采集轨迹、评分、生成报告
```

---

## 完整数据流：hooks 与其他概念的关系

```
┌─────────────────────────────────────────────────────────────┐
│                     你的 Agent 项目                          │
│                                                             │
│   业务代码 ──emit.retrieval()──▶ agent-hooks SDK            │
│   业务代码 ──emit.llm_call()──▶                             │
│   业务代码 ──emit.tool_call()──▶                            │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              agent-hooks SDK（桥梁层）                       │
│                                                             │
│   emit 实例 ──▶ _hooks.on_retrieval()                       │
│                                                             │
│   默认: NoOpHooks（空操作，零开销）                           │
│   集成时: register(EvalHooks()) 替换为有实际行为的实现        │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  评估平台（你不需要写这部分）                  │
│                                                             │
│   EvalHooks.on_retrieval()                                  │
│       └──▶ TrajectoryCollector（轨迹收集器）                 │
│               └──▶ record_retrieval()                       │
│                       └──▶ 存储到数据库                      │
│                                                             │
│   EvalHooks.on_session_end()                                │
│       └──▶ collector.finish()                               │
│               └──▶ 触发 6 个评估器并行运行                   │
│                       ├──▶ planning_evaluator（规划质量）    │
│                       ├──▶ tactical_evaluator（战术决策）    │
│                       ├──▶ tool_use_evaluator（工具使用）    │
│                       ├──▶ memory_evaluator（记忆保持）      │
│                       ├──▶ replan_evaluator（重规划）        │
│                       └──▶ retrieval_evaluator（检索质量）   │
│                               └──▶ 生成评估报告              │
│                                       └──▶ 前端可视化展示    │
└─────────────────────────────────────────────────────────────┘
```

### 各层职责

| 层 | 是什么 | 谁提供 | 职责 |
|---|--------|--------|------|
| **emit 调用** | 业务代码中的 `await emit.xxx()` | **你** | 报告"我做了什么" |
| **AgentHooks 接口** | 标准化的事件协议（Protocol） | agent-hooks SDK | 定义事件格式 |
| **NoOpHooks** | 默认空操作实现 | agent-hooks SDK | 独立运行时零开销 |
| **Emitter** | 事件发射器 | agent-hooks SDK | 注册 + 触发 + 异常隔离 |
| **EvalHooks** | 评估平台的 hooks 实现 | 评估平台 | 把事件转为评估数据 |
| **TrajectoryCollector** | 轨迹收集器 | 评估平台 | 存储和上报轨迹 |
| **评估器** | 6 个 LLM-as-Judge | 评估平台 | 对轨迹打分 |
| **评估报告** | 可视化界面 | 评估平台前端 | 展示评分结果 |

---

## API 参考

### 事件列表

| 事件方法 | 触发时机 | 参数 | 说明 |
|----------|----------|------|------|
| `emit.session_start()` | 会话/任务开始 | `goal, session_id, context` | 标记一次 Agent 运行的开始 |
| `emit.llm_call()` | LLM 调用完成 | `model, messages, response, usage` | 记录 LLM 输入输出 |
| `emit.tool_call()` | 工具调用完成 | `tool_name, args, result, duration_ms` | 记录工具使用 |
| `emit.retrieval()` | RAG 检索完成 | `query, results, duration_ms` | 记录检索结果 |
| `emit.key_facts()` | 提取/写入记忆 | `facts, scope` | 记录记忆操作 |
| `emit.response()` | 生成回复 | `session_id, response` | 记录最终回复 |
| `emit.error()` | 发生错误 | `session_id, error` | 记录异常 |
| `emit.session_end()` | 会话结束 | `session_id` | 标记一次运行结束 |

### 核心对象

```python
from agent_hooks import emit      # 全局 Emitter 实例（直接用这个）
from agent_hooks import register   # 注册 hooks 实现
from agent_hooks import AgentHooks # Protocol 接口（评估平台实现）
from agent_hooks import NoOpHooks  # 默认空操作实现
from agent_hooks import Emitter    # Emitter 类（高级用法：创建独立实例）
```

### 高级用法：独立 Emitter 实例

如果需要多个独立的 hooks 注册表（如多 Agent 系统）：

```python
from agent_hooks import Emitter, AgentHooks

# 创建独立实例
agent_a_emit = Emitter()
agent_b_emit = Emitter()

# 分别注册不同的 hooks
agent_a_emit.register(MyAgentAHooks())
agent_b_emit.register(MyAgentBHooks())

# 使用
await agent_a_emit.retrieval(query, results, 100.0)
await agent_b_emit.retrieval(query, results, 200.0)
```

---

## 接入模式

### 模式 1：全量接入（推荐）

在 Agent 生命周期的所有关键节点添加 emit 调用，获得最完整的评估数据。

```python
from agent_hooks import emit

async def process(goal, session_id):
    await emit.session_start(goal, session_id, ctx)

    # ... 检索、LLM 调用、工具使用 ...

    await emit.response(session_id, answer)
    await emit.session_end(session_id)
```

### 模式 2：最小接入

只在会话开始和结束时调用，评估平台仍能采集基本轨迹。

```python
from agent_hooks import emit

async def process(goal, session_id):
    await emit.session_start(goal, session_id, {})
    # ... Agent 逻辑 ...
    await emit.session_end(session_id)
```

### 模式 3：渐进接入

先添加基本事件，后续逐步补充更多细节。

```python
# 第 1 阶段：会话生命周期
await emit.session_start(...)
await emit.session_end(...)

# 第 2 阶段：添加检索
await emit.retrieval(...)

# 第 3 阶段：添加 LLM 调用
await emit.llm_call(...)

# 第 4 阶段：添加工具调用
await emit.tool_call(...)
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
        thought = await think(goal, context)
        await emit.llm_call("my-llm", context, thought)

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

## 与现有 SDK 的关系

| | agent-hooks | sdk/ (LangGraph Adapter) |
|---|---|---|
| **定位** | 通用生命周期钩子 | LangGraph 专用自动采集 |
| **侵入性** | 手动在关键点调用 | 一行代码自动采集 |
| **框架依赖** | 无（任何框架） | LangGraph / LangChain |
| **采集粒度** | Agent 自定义 | 节点/状态/工具/LLM 自动 |
| **适用场景** | 任意 Agent 项目 | LangGraph 项目 |

**可以同时使用**：LangGraph 项目可以用 `sdk/` 自动采集内部细节，同时用 `agent-hooks` 记录业务层语义事件。

---

## 不安装时的降级方案

如果不想强制依赖 agent-hooks，可以在项目中提供 fallback：

```python
# my_agent/hooks.py
try:
    from agent_hooks import emit
except ImportError:
    class _NoOpEmit:
        """agent-hooks 未安装时的降级实现"""
        def __getattr__(self, name: str):
            async def _noop(*args, **kwargs):
                pass
            return _noop
    emit = _NoOpEmit()

# 业务代码统一 import
from my_agent.hooks import emit
```

这样即使没安装 agent-hooks，Agent 也能正常运行。

---

## 设计原则

- **零依赖**：只用 Python 标准库（`logging`, `typing`）
- **零侵入**：Agent 项目只调用 `emit.*()`，不实现任何接口
- **可选**：不安装时 Agent 正常运行
- **异常隔离**：hooks 出错不影响 Agent 主流程（try/except 保护）
- **框架无关**：适用于 LangGraph、AutoGen、CrewAI、自研框架等任何 Agent

---

## License

MIT
