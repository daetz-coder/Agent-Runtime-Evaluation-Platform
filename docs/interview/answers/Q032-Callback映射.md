# Q32: Callback adapter 能捕获哪些事件？LangChain 的 `on_llm_start` / `on_tool_end` 如何映射到 ActionType？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q032 |
| 分类 | 轨迹（Trajectory）与埋点 |
| 难度 | ★ |

## 问题

Callback adapter 能捕获哪些事件？LangChain 的 `on_llm_start` / `on_tool_end` 如何映射到 ActionType？

## 参考答案

Q32 与 Callback 映射 相关。on_llm_start→think；on_tool_start/end→tool_call/result Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。轨迹是六维 Judge 的唯一输入，ActionType 契约在 app/models/action_types.py 与 sdk/collector.py 双处维护。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。

## 代码依据

- `sdk/adapters/callback.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- Callback 映射：on_llm_start→think
- 代码入口：sdk/adapters/callback.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「Callback 映射」最先看哪段代码？**

A: 打开 sdk/adapters/callback.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 Callback 映射？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q031](../answers/Q031-LangGraph包装.md)
- [Q033](../answers/Q033-LLM-Proxy幂等.md)
