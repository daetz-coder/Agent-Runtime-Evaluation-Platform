# SDK — 轨迹采集与自动评估

> **入口**: [README.md](../README.md) · **集成指南**: [docs/adapters.md](../docs/adapters.md) · **API**: [docs/api.md](../docs/api.md)

---

零侵入 Agent 运行时轨迹收集 + 自动评估接入。

## 安装

```bash
# 从项目根目录安装
pip install -e .

# 或手动安装依赖
pip install httpx langchain-core langgraph
```

## 快速接入

### 方式 1：LangGraph 自动采集（推荐）

```python
from sdk import instrument_langgraph, create_proxy_llm, get_collector

# 包裹 LLM（自动记录 LLM 调用、工具决策）
llm = create_proxy_llm(ChatOpenAI(model="gpt-4"))

# 包裹 Graph（自动记录节点执行、状态变化、工具调用、失败）
graph = instrument_langgraph(build_graph())

# 生命周期
collector = get_collector()
collector.start("用户目标", {"key_facts": ["项目用JWT"]})
result = await graph.ainvoke(state, config)
collector.finish(auto_run=True)  # flush + 触发评估
```

### 方式 2：LangChain Callback

```python
from sdk import create_callback_handler

handler = create_callback_handler()
llm = ChatOpenAI(callbacks=[handler])
```

### 方式 3：手动记录（非 LangChain 框架）

```python
from sdk import get_collector, ActionType

collector = get_collector()
collector.start("修复登录 bug")

collector.record_think("分析 JWT 过期问题")
collector.record_tool_call("search_code", {"query": "JWT expiry"})
collector.record_tool_result("search_code", {"files": ["auth.py"]})
collector.record_replan(reason="JWT 库版本不兼容", new_plan="升级到 v2.0")
collector.record_memory_write("jwt_version", "2.0", source="discovery")
collector.record_retrieval("JWT 配置", [{"title": "auth.md", "snippet": "..."}])
collector.record_failure("ImportError", "jwt v1 not found", recoverable=True)

collector.finish(auto_run=True)
```

## 配置

通过环境变量配置，无需修改代码：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `EVAL_ENABLED` | `true` | 总开关 |
| `EVAL_API_BASE_URL` | `http://127.0.0.1:8000` | 评估平台地址 |
| `EVAL_API_KEY` | `""` | API 认证密钥 |
| `EVAL_BATCH_SIZE` | `10` | 批量上传阈值 |

## 14 种 Action Type

| 方法 | Action Type | 说明 |
|------|-------------|------|
| `start()` 自动记录 | `plan` | 初始规划 |
| `record_plan_update()` | `plan_update` | 动态规划更新 |
| `record_tool_call()` | `tool_call` | 工具调用 |
| `record_tool_result()` | `tool_result` | 工具返回 |
| `record_memory_write()` | `memory_write` | 记忆写入 |
| `record_memory_read()` | `memory_read` | 记忆读取 |
| `record_state_change()` | `state_change` | 状态变化 |
| `record_think()` | `think` | 思考过程 |
| `record_replan()` | `replan` | 重规划 |
| `record_failure()` | `failure` | 失败/异常 |
| `record_node_execute()` | `node_execute` | 节点执行 |
| `record_llm_call()` | `think` | LLM 调用 |
| `record_retrieval()` | `retrieval` | 知识检索 |
| `record_evidence()` | `evidence` | 证据构建 |

## 任务管理

```python
collector = get_collector()

# 创建任务
task_id = collector.start("目标")

# 中途更新上下文（如追加 key_facts）
collector.update_task(context={"key_facts": ["事实1", "事实2"]})

# 更新状态
collector.update_task(status="running")

# 结束 + 触发评估
collector.finish(auto_run=True)

# 重置（多次评估场景）
collector.reset()

# 释放资源
collector.close()
```

## 容错机制

- **离线模式**：平台不可达时轨迹缓冲在内存，不阻塞 Agent 运行
- **指数退避重试**：HTTP 请求失败自动重试 3 次（0.5s → 1s → 2s）
- **失败回退缓冲**：flush 失败时步骤回退到本地缓冲，下次 flush 重试
- **错误日志**：所有失败记录到 `sdk.collector` logger，不再静默吞异常
- **有界去重**：`_seen_events` 上限 5000 条，避免长任务内存泄漏
