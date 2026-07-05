# Q025: 请说明 `sdk/collector.py` 的 TrajectoryCollector 如何统一所有 Agent 的轨迹采集？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q025 |
| 分类 | 轨迹与埋点 |
| 难度 | ★★ |

## 问题

请说明 `sdk/collector.py` 的 TrajectoryCollector 如何统一所有 Agent 的轨迹采集？HTTP 模式如何避免自死锁？

## 参考答案

项目中所有 Agent（Wiki Agent、Sandbox Agent、外部 Agent）统一使用 `sdk/collector.py` 的 `TrajectoryCollector` 进行轨迹采集。

**统一架构。** TrajectoryCollector 是单例模式，通过 `get_collector()` 获取。所有 Agent 调用相同的 `record_*()` 方法记录轨迹，通过 HTTP POST 推送到评估平台。

**HTTP 模式避免自死锁。** Wiki Agent 运行在与平台相同的 FastAPI 进程中。如果直接在事件循环中发 HTTP 请求到 localhost，会阻塞事件循环导致自死锁。解决方案是使用 `asyncio.to_thread()` 将 HTTP 请求放到独立线程池中执行：

```python
async def start_async(self, goal, context):
    return await asyncio.to_thread(self.start, goal, context)

async def finish_async(self, *, auto_run=False):
    return await asyncio.to_thread(self.finish, auto_run=auto_run)
```

`asyncio.to_thread()` 将同步的 HTTP 请求放到线程池中执行，不阻塞主事件循环，评估平台的 API 可以正常处理请求。

**Pydantic Schema 校验。** 每种 ActionType 都有对应的 Pydantic 模型（`sdk/schemas.py`），`record()` 方法在写入前自动调用 `model_validate()` 校验格式：

```python
def _validate_step(action_type, action_detail):
    schema_class = ACTION_DETAIL_SCHEMAS.get(action_type)
    if schema_class:
        schema_class.model_validate(action_detail)
```

**14 种 ActionType 完整覆盖。** 两个 Agent 都覆盖了全部 14 种 ActionType：
- PLAN, PLAN_UPDATE, TOOL_CALL, TOOL_RESULT, TOOL_DECISION
- MEMORY_WRITE, MEMORY_READ, STATE_CHANGE, NODE_EXECUTE
- THINK, FAILURE, REPLAN, RETRIEVAL, EVIDENCE

## 代码依据

- `sdk/collector.py` — TrajectoryCollector 单例，record() 方法，start_async/finish_async
- `sdk/schemas.py` — 14 种 ActionType 的 Pydantic 模型
- `app/wiki_agent/hooks.py` — Wiki Agent 通过 hooks 调用 collector
- `app/agent_runtime/runner.py` — Sandbox Agent 直接使用 collector
- `app/wiki_agent/agent/graph.py` — 补充了 NODE_EXECUTE, STATE_CHANGE, TOOL_DECISION 等记录

## 回答要点

- 统一使用 TrajectoryCollector，不再有 in-process transport
- HTTP 模式通过 `asyncio.to_thread()` 避免自死锁
- Pydantic Schema 校验保证数据格式
- 14 种 ActionType 完整覆盖

## 相关题目

- [Q013](../answers/Q013-轨迹驱动评估.md)
- [Q030](../answers/Q030-低侵入埋点.md)
