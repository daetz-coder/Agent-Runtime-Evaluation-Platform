# Q123: 「零侵入 SDK 接入」的具体含义是什么？开发者最少需要改几行代码？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q123 |
| 分类 | SDK 与零侵入接入 |
| 难度 | ★★ |

## 问题

「零侵入 SDK 接入」的具体含义是什么？开发者最少需要改几行代码？

## 参考答案

「零侵入」意味着开发者无需修改任何 Agent 业务逻辑，只需在现有代码中添加一行包装调用，SDK 即通过透明代理自动采集全部运行数据。最少改动为 **1 行代码**。

**LangGraph 适配器。** 开发者在 `graph.compile()` 之前插入一行 `graph = instrument_langgraph(graph)`（`langgraph.py:378-410`）。该函数遍历图中所有节点，在每个节点的 `invoke` 前后插入 trace 采集逻辑，自动记录节点名、输入 state、输出 state 和耗时。开发者原图定义、节点函数、边条件均不需要改动。

**LLM Proxy 适配器。** 对于非 LangGraph 场景，开发者在绑定工具之前插入一行 `llm = create_proxy_llm(llm)`（`llm_proxy.py:240-266`）。Proxy 对象包装了原始 LLM 的 `invoke`/`ainvoke`/`stream`/`astream` 四个方法，在每次调用时自动记录 prompt、response、token 用量和延迟，同时转发至后端 Collector。

**Callback Handler。** 如果开发者使用 LangChain 的 Chain/Agent，可以附加 `create_callback_handler()`（`callback.py:288-307`）到 LLM 实例。Handler 实现标准 `BaseCallbackHandler` 接口，在 `on_llm_start`、`on_llm_end`、`on_tool_start`、`on_tool_end` 等回调中采集数据。

**自动触发评估。** 当 Agent 运行结束后，`Collector.finish(auto_run=True)`（`collector.py:308-335`）自动将采集到的 trace 数据提交给评估 API，无需开发者手动调用。如果 `auto_run=False`，开发者可手动调用 `collector.submit()` 触发。

SDK 的核心设计原则是：所有采集逻辑封装在适配器内部，Agent 代码保持纯净，不引入平台依赖。三种适配器将框架事件统一映射到 14 种 `ActionType`，保证评估器拿到的轨迹 schema 一致。

## 代码依据

- `sdk/adapters/langgraph.py:378-410` — `instrument_langgraph()` 一行包装 LangGraph 图
- `sdk/adapters/llm_proxy.py:240-266` — `create_proxy_llm()` 一行代理 LLM
- `sdk/adapters/callback.py:288-307` — `create_callback_handler()` 回调方式采集
- `sdk/collector.py:308-335` — `finish(auto_run=True)` 自动触发评估

## 回答要点

- 零侵入 = 不改 Agent 业务逻辑，只加一行包装调用，最少 1 行代码
- 三种接入方式：LangGraph instrument、LLM Proxy、Callback Handler，适配不同场景
- SDK 通过 Python 的动态代理/装饰器模式透明拦截所有 LLM 和 Tool 调用
- `Collector.finish(auto_run=True)` 自动提交评估，形成采集到评估的闭环
- 三种适配器统一映射到 14 种 ActionType，保证评估器输入 schema 一致

## 常见追问

**Q: 如果开发者同时用了 LangGraph 和独立的 LLM 调用，怎么采集？**

A: LangGraph instrument 只覆盖图内节点。对于图外的独立 LLM 调用，需要额外用 `create_proxy_llm()` 包装，两者不冲突，Collector 会合并同一 session 的所有 trace。

**Q: 代理模式会不会影响 LLM 调用性能？**

A: Proxy 层只做事件记录和数据转发，不做同步网络请求（Collector 采用异步缓冲批量上报，受 `EVAL_BATCH_SIZE` 控制）。实测额外延迟 < 1ms，对 LLM 调用延迟（通常数百毫秒到数秒）可忽略。

**Q: 三种适配器怎么选？**

A: LangGraph Agent 用 `instrument_langgraph`；纯 LangChain Chain 用 Callback Handler；自定义 Agent 或其他框架用 `create_proxy_llm`。可以混合使用，Collector 统一汇聚。

## 相关题目

- [Q122](../answers/Q122-EVAL_AUTO_RUN.md)
- [Q124](../answers/Q124-adapter路径.md)
