# agent-hooks

轻量级 Agent 生命周期钩子 SDK — 零依赖、零侵入的评估接入方案。

## 安装

```bash
pip install -e agent-hooks/
```

## Agent 项目接入

只需 2 步：

### 1. 在关键节点调用 emit

```python
from agent_hooks import emit

# 会话开始
await emit.session_start(goal, session_id, context)

# LLM 调用
await emit.llm_call(model, messages, response, usage)

# 工具调用
await emit.tool_call("search", {"query": "..."}, result, duration_ms)

# RAG 检索
await emit.retrieval(query, results, duration_ms)

# 提取事实/记忆
await emit.key_facts(facts, scope="session")

# 生成回复
await emit.response(session_id, response)

# 发生错误
await emit.error(session_id, exception)

# 会话结束
await emit.session_end(session_id)
```

### 2. 提供降级方案（可选）

如果不想强制依赖 agent-hooks，可以提供本地 fallback：

```python
# my_agent/hooks_compat.py
try:
    from agent_hooks import emit
except ImportError:
    class _NoOp:
        def __getattr__(self, name):
            async def _noop(*a, **kw):
                pass
            return _noop
    emit = _NoOp()

# 业务代码统一用：
from my_agent.hooks_compat import emit
```

## 评估平台接入

评估平台实现 `AgentHooks` 接口，在启动时注册：

```python
from agent_hooks import AgentHooks, register

class EvalHooks(AgentHooks):
    async def on_session_start(self, goal, session_id, context):
        # 创建评估任务
        ...

    async def on_retrieval(self, query, results, duration_ms):
        # 记录检索轨迹
        ...

    async def on_response(self, session_id, response):
        # 记录回复
        ...

    async def on_session_end(self, session_id):
        # 结束评估
        ...

# 注册（评估平台启动时调用一次）
register(EvalHooks())
```

只需实现关心的事件，其余自动降级为空操作。

## 事件列表

| 事件方法 | 触发时机 | 参数 |
|----------|----------|------|
| `on_session_start` | 会话/任务开始 | goal, session_id, context |
| `on_llm_call` | LLM 调用完成 | model, messages, response, usage |
| `on_tool_call` | 工具调用完成 | tool_name, args, result, duration_ms |
| `on_retrieval` | RAG 检索完成 | query, results, duration_ms |
| `on_key_facts` | 提取/写入记忆 | facts, scope |
| `on_response` | 生成回复 | session_id, response |
| `on_error` | 发生错误 | session_id, error |
| `on_session_end` | 会话结束 | session_id |

## 设计原则

- **零依赖**：只用 Python 标准库
- **零侵入**：agent 项目只调用 `emit.*()`，不定义接口
- **可选**：不安装时 agent 正常运行
- **异常隔离**：hooks 出错不影响 agent 主流程
