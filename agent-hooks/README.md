# agent-hooks

轻量级 Agent 生命周期钩子 SDK — 零依赖、零侵入的评估接入方案。

任何 Agent 项目只需 `pip install agent-hooks` + 在关键节点调用 `await emit.xxx()`，即可接入 Agent Runtime Evaluation Platform 进行全维度质量评估。

---

## 目录

- [安装](#安装)
- [两层接口设计](#两层接口设计)
- [快速开始](#快速开始)
- [你需要提供什么](#你需要提供什么)
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

## 两层接口设计

不同 Agent 有不同的架构，有的有检索、有的有工具、有的只有 LLM。为了**适配所有类型的 Agent**，提供两层接口：

### 通用层 — 任何 Agent 都能用

不需要 Agent 有特定组件，只需要在"做了某件事"时调用：

```python
from agent_hooks import emit

# 方式 1：trace — 结构化但灵活，action 自定义
await emit.trace(
    action="search",                              # 你自己定义的类型名
    input={"query": "Python 异步编程"},             # 输入（可选）
    output={"results": [...], "count": 5},         # 输出（可选）
    duration_ms=150,                               # 耗时（可选）
)

# 方式 2：step — 最简单，一句话描述
await emit.step("检索知识库", "查询 Python 异步编程，返回 5 条结果")
```

**适用场景**：
- 自研框架，不想适配固定事件格式
- Agent 架构特殊（如 Multi-Agent、Workflow Agent）
- 快速接入，不想改太多代码

### 结构化层 — 提供更精确的评估

如果 Agent 有明确的组件（检索、工具、LLM），可以用结构化事件获得更精确的评估：

```python
# RAG Agent：用 retrieval 记录检索
await emit.retrieval(query, results, duration_ms=120)

# 工具 Agent：用 tool_call 记录工具调用
await emit.tool_call("code_executor", {"code": "print(1)"}, result, duration_ms=300)

# LLM Agent：用 llm_call 记录 LLM 调用
await emit.llm_call("gpt-4", messages, response, usage={"tokens": 500})

# 记忆 Agent：用 key_facts 记录记忆操作
await emit.key_facts(["用户偏好 Python", "项目使用 asyncio"], scope="session")
```

**适用场景**：
- RAG Agent（有检索组件）
- 工具 Agent（有工具调用）
- 需要精确评估某个维度

### 两层可以混用

```python
await emit.session_start(goal, session_id, ctx)

# 结构化事件：精确记录检索
results = await search(query)
await emit.retrieval(query, results, 120)

# 通用 trace：记录自定义操作
await emit.trace("validate", input={"data": data}, output={"valid": True})

# 结构化事件：精确记录 LLM 调用
response = await llm.ainvoke(messages)
await emit.llm_call(model, messages, response.content)

# 最终回复
await emit.response(session_id, answer)
await emit.session_end(session_id)
```

### 选择指南

```
你的 Agent 有检索/工具/LLM 组件吗？
│
├─ 有 → 用结构化层（emit.retrieval / tool_call / llm_call）
│       评估更精确，维度评分更准确
│
└─ 没有 / 不确定 / 想快速接入
    │
    ├─ 想要结构化数据 → 用 emit.trace(action, input, output)
    │                   action 名自定义，评估平台用 LLM 理解
    │
    └─ 想要最简单 → 用 emit.step(name, detail)
                    一句话描述，评估平台用 LLM 分析
```

---

## 快速开始

### 第 1 步：安装

```bash
pip install -e agent-hooks/
```

### 第 2 步：在 Agent 代码中添加 emit 调用

**最简接入（2 行代码）：**

```python
from agent_hooks import emit

async def run_agent(goal: str, session_id: str):
    await emit.session_start(goal, session_id, {"agent": "my-agent"})

    # ... 你的 Agent 逻辑 ...
    # 在关键位置加 emit.step() 或 emit.trace()

    await emit.step("检索", f"查询 {query}，返回 {len(results)} 条")
    await emit.step("生成回复", f"{len(answer)} 字")

    await emit.session_end(session_id)
```

**完整接入（精确评估）：**

```python
from agent_hooks import emit

async def run_agent(goal: str, session_id: str):
    await emit.session_start(goal, session_id, {"agent": "my-agent"})

    results = await search(query)
    await emit.retrieval(query, results, duration_ms=150)

    response = await llm.ainvoke(messages)
    await emit.llm_call(model, messages, response.content)

    await emit.response(session_id, final_answer)
    await emit.session_end(session_id)
```

### 第 3 步：正常运行

```bash
python my_agent.py
```

独立运行时，所有 emit 调用自动降级为空操作，**零开销**。

---

## 你需要提供什么

### 你负责的（最少 2 件事）

1. `pip install agent-hooks`
2. 在关键位置加 `await emit.xxx()`

```python
from agent_hooks import emit

# 会话生命周期（必须）
await emit.session_start(goal, session_id, ctx)
# ... Agent 逻辑 ...
await emit.session_end(session_id)

# 关键操作（选一种方式）
await emit.retrieval(query, results, ms)   # 结构化（精确）
await emit.trace("search", input=..., output=...)  # 通用（灵活）
await emit.step("检索", "返回 5 条")       # 最简（一句话）
```

### 评估平台已提供的（不需要你写）

| 组件 | 说明 | 谁提供 |
|------|------|--------|
| `AgentHooks` 接口 | 标准化的事件协议 | agent-hooks SDK |
| `NoOpHooks` 默认实现 | 独立运行时的空操作 | agent-hooks SDK |
| `Emitter` 事件发射器 | 注册 + 触发 + 异常隔离 + trace 缓冲 | agent-hooks SDK |
| `EvalHooks` 实现 | 把事件转为评估数据 | 评估平台 |
| LLM 分类器 | 理解 trace/step 内容，归类到评估维度 | 评估平台 |
| 6 个评估器 | LLM-as-Judge 评分 | 评估平台 |
| 评估报告 | 可视化展示 | 评估平台前端 |

---

## API 参考

### 通用层（任何 Agent 都能用）

| 方法 | 说明 | 参数 |
|------|------|------|
| `emit.trace()` | 结构化追踪记录 | `action, input, output, duration_ms, meta` |
| `emit.step()` | 步骤记录（一句话） | `name, detail, status` |

### 会话生命周期

| 方法 | 说明 | 参数 |
|------|------|------|
| `emit.session_start()` | 会话开始 | `goal, session_id, context` |
| `emit.session_end()` | 会话结束 | `session_id` |

### 结构化层（可选，更精确的评估）

| 方法 | 说明 | 参数 |
|------|------|------|
| `emit.llm_call()` | LLM 调用 | `model, messages, response, usage` |
| `emit.tool_call()` | 工具调用 | `tool_name, args, result, duration_ms` |
| `emit.retrieval()` | RAG 检索 | `query, results, duration_ms` |
| `emit.key_facts()` | 记忆操作 | `facts, scope` |
| `emit.response()` | 最终回复 | `session_id, response` |
| `emit.error()` | 错误记录 | `session_id, error` |

### 核心对象

```python
from agent_hooks import emit      # 全局 Emitter 实例
from agent_hooks import register   # 注册 hooks 实现
from agent_hooks import AgentHooks # Protocol 接口
from agent_hooks import NoOpHooks  # 默认空操作实现
from agent_hooks import Emitter    # Emitter 类（高级用法）
```

### Trace 缓冲

Emitter 会自动缓存最近会话的 trace 记录，可用于调试：

```python
# 查看缓冲
print(emit.trace_buffer)  # [{'action': 'search', 'input': {...}, ...}, ...]

# 清空缓冲（session_start 时自动清空）
emit.clear_buffer()
```

---

## 接入模式

### 模式 1：最小接入（step 只需 2 行）

```python
await emit.session_start(goal, session_id, ctx)
# ... Agent 逻辑 ...
await emit.step("生成回复", f"{len(answer)} 字")
await emit.session_end(session_id)
```

### 模式 2：通用接入（trace 结构化）

```python
await emit.session_start(goal, session_id, ctx)
await emit.trace("search", input={"query": q}, output={"count": 5}, duration_ms=120)
await emit.trace("generate", input={"prompt": p}, output={"text": t})
await emit.session_end(session_id)
```

### 模式 3：精确接入（结构化事件）

```python
await emit.session_start(goal, session_id, ctx)
await emit.retrieval(query, results, 120)
await emit.llm_call(model, messages, response)
await emit.tool_call("executor", args, result, 300)
await emit.response(session_id, answer)
await emit.session_end(session_id)
```

### 模式 4：混合接入（推荐）

```python
await emit.session_start(goal, session_id, ctx)

# 有明确组件的用结构化事件
await emit.retrieval(query, results, 120)
await emit.llm_call(model, messages, response)

# 自定义操作用 trace
await emit.trace("validate", input={"data": d}, output={"valid": True})

# 补充上下文用 step
await emit.step("用户确认", "用户选择方案 A")

await emit.response(session_id, answer)
await emit.session_end(session_id)
```

---

## 各框架接入示例

### RAG Agent

```python
from agent_hooks import emit

await emit.session_start(goal, session_id, {"agent": "rag-agent"})

results = await vector_store.search(query)
await emit.retrieval(query, results, 120)       # 结构化：精确评估检索质量

response = await llm.ainvoke(context + query)
await emit.llm_call(model, messages, response.content)

await emit.response(session_id, response.content)
await emit.session_end(session_id)
```

### Code Agent

```python
from agent_hooks import emit

await emit.session_start(goal, session_id, {"agent": "code-agent"})

plan = await llm.ainvoke("分析需求：" + goal)
await emit.llm_call(model, messages, plan.content)

code = extract_code(plan)
result = await sandbox.execute(code)
await emit.tool_call("sandbox", {"code": code}, result, duration_ms=5000)

await emit.response(session_id, result.output)
await emit.session_end(session_id)
```

### Chat Agent（最简单）

```python
from agent_hooks import emit

await emit.session_start(goal, session_id, {"agent": "chat-agent"})

response = await llm.ainvoke(messages)
await emit.llm_call(model, messages, response.content)

await emit.response(session_id, response.content)
await emit.session_end(session_id)
```

### Workflow Agent（通用层）

```python
from agent_hooks import emit

await emit.session_start(goal, session_id, {"agent": "workflow-agent"})

# 用 trace 记录每一步
for step in workflow.steps:
    result = await step.execute(context)
    await emit.trace(step.name, input=step.input, output=result, duration_ms=result.ms)

await emit.response(session_id, final_result)
await emit.session_end(session_id)
```

### Multi-Agent（通用层 + step）

```python
from agent_hooks import emit

await emit.session_start(goal, session_id, {"agent": "multi-agent"})

# 用 step 记录每个子 Agent 的工作
await emit.step("规划 Agent", "生成 3 步执行计划")
await emit.step("检索 Agent", "搜索知识库，返回 10 条结果")
await emit.step("执行 Agent", "运行代码，测试通过")

await emit.response(session_id, final_answer)
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
        def __getattr__(self, name: str):
            async def _noop(*args, **kwargs):
                pass
            return _noop
    emit = _NoOpEmit()

# 业务代码统一 import
from my_agent.hooks import emit
```

---

## 设计原则

- **零依赖**：只用 Python 标准库（`logging`, `typing`）
- **零侵入**：Agent 项目只调用 `emit.*()`，不实现任何接口
- **两层适配**：通用层（任何 Agent）+ 结构化层（精确评估）
- **可选**：不安装时 Agent 正常运行
- **异常隔离**：hooks 出错不影响 Agent 主流程
- **框架无关**：LangGraph、AutoGen、CrewAI、自研框架都能用

---

## License

MIT
