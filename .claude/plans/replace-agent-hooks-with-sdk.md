# 移除 agent-hooks，统一使用 SDK

## 目标
1. 删除 `agent-hooks/` 目录
2. 重写 `app/wiki_agent/hooks.py`，使用 SDK 的 `TrajectoryCollector`
3. 更新引用 agent-hooks 的文档

## 当前架构
```
graph.py → hooks.py → agent-hooks SDK (emit.*)
```

## 目标架构
```
graph.py → hooks.py → SDK TrajectoryCollector (record_*)
```

## 关键映射：hooks emit → SDK collector

| hooks 函数 | SDK 方法 | 说明 |
|---|---|---|
| `emit_session_start(goal, sid, ctx)` | `await collector.start_async(goal, ctx)` | 返回 task_id，内部自动记录 PLAN |
| `emit_retrieval(query, results, ms)` | `await collector.record_retrieval(query, results, duration_ms=ms)` | 直接对应 |
| `emit_key_facts(facts)` | `await collector.record_memory_write("key_facts", facts, source="llm_extraction")` | 语义近似 |
| `emit_response(sid, response)` | `await collector.record(ActionType.EVIDENCE, {"final_response": response})` | 用 EVIDENCE 记录最终回复 |
| `emit_session_end(sid)` | `await collector.finish_async(auto_run=True)` | flush + 触发评估 |
| `emit_trace(action, ...)` | `await collector.record(action, {...})` | 通用层 |
| `emit_step(name, detail)` | `await collector.record_think(f"{name}: {detail}")` | 步骤记录 |

## 离线/无平台行为
SDK collector 已内置：
- `EVAL_ENABLED=false` → 所有操作静默跳过
- 平台不可达 → 本地缓冲 + 指数退避重试
- 嵌入模式（localhost）→ 直接写 DB，不走 HTTP

## 执行步骤

### Step 1: 重写 `app/wiki_agent/hooks.py`
- 从 `sdk.collector` 导入 `get_collector`, `ActionType`
- 保持 `graph.py` 使用的 5 个 emit 函数签名不变
- 保留 `emit_trace` 和 `emit_step` 供未来使用
- 不依赖 agent-hooks

### Step 2: 删除 `agent-hooks/` 目录
- `rm -rf agent-hooks/`

### Step 3: 更新文档
- `README.md` — 移除 agent-hooks 相关行
- `docs/agent-hooks-integration.md` — 删除此文件
- `docs/adapters.md` — 移除 agent-hooks 引用
- `docs/wiki-agent-overview.md` — 更新 hooks 描述
- `docs/wiki-agent-difficult-points.md` — 更新难点 9 描述
- `docs/wiki-agent-learning-guide.md` — 更新第八阶段描述
- `docs/wiki-agent-optimization-report.md` — 更新 hooks 描述
- `app/wiki_agent/README.md` — 更新 hooks 示例

### Step 4: 验证
- 确认 `graph.py` 的 import 仍正常工作
- 确认 `from sdk.collector import get_collector` 可用

## 不需要改的文件
- `app/wiki_agent/agent/graph.py` — 只 import hooks.py，不直接引用 agent-hooks
- `app/models/action_types.py` — 已经从 sdk re-export
- `sdk/` — 保持不变
