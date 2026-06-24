# Q34: 如果 Agent 内部有自定义工具（非 LangChain Tool），如何手动调用 collector 上报？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q034 |
| 分类 | 轨迹（Trajectory）与埋点 |
| 难度 | ★ |

## 问题

如果 Agent 内部有自定义工具（非 LangChain Tool），如何手动调用 collector 上报？

## 参考答案

围绕 手动 collector：get_collector().record_tool_call/record_retrieval 等 14 种 API 面试回答应先说业务场景，再落到 sdk/collector.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。轨迹是六维 Judge 的唯一输入，ActionType 契约在 app/models/action_types.py 与 sdk/collector.py 双处维护。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。

## 代码依据

- `sdk/collector.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- 手动 collector：get_collector().record_tool_call/record_retrieval 等 14 种 API
- 代码入口：sdk/collector.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「手动 collector」最先看哪段代码？**

A: 打开 sdk/collector.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 手动 collector？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q033](../answers/Q033-LLM-Proxy幂等.md)
- [Q035](../answers/Q035-显式vs自动埋点.md)
