# agent-hooks

轻量级 Agent 生命周期钩子 SDK — 零依赖、零侵入的评估接入方案。

任何 Agent 项目只需 `pip install agent-hooks` + 在关键节点调用 `await emit.xxx()`，即可接入 Agent Runtime Evaluation Platform 进行全维度质量评估。

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

在评估平台启动时注册 hooks：

```python
# eval_platform/hooks_impl.py
from agent_hooks import AgentHooks

class EvalHooks(AgentHooks):
    async def on_session_start(self, goal, session_id, context):
        # 创建评估任务
        self.task_id = collector.start(goal, context)

    async def on_retrieval(self, query, results, duration_ms):
        # 记录检索轨迹
        collector.record_retrieval(query=query, retrieved_docs=results)

    async def on_response(self, session_id, response):
        # 记录回复
        collector.record_response(response)

    async def on_session_end(self, session_id):
        # 结束评估
        collector.finish(auto_run=True)
```

```python
# eval_platform/main.py 启动时
from agent_hooks import register
from eval_platform.hooks_impl import EvalHooks

register(EvalHooks())
```

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
