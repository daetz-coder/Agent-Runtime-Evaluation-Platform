# Q45: 如果未来要在 LangGraph 里实现真正的并行评估节点，你会怎么改 State 设计？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q045 |
| 分类 | LangGraph 与工作流编排 |
| 难度 | ★ |

## 问题

如果未来要在 LangGraph 里实现真正的并行评估节点，你会怎么改 State 设计？

## 参考答案

问题「如果未来要在 LangGraph 里实现真正的并行评估节点，你会怎么改 State 设计？」考察 真并行 State 改造。用 Annotated reducer 或子 state 分片再 aggregate LangGraph 同时服务评估 workflow（evaluation_graph.py）与 Wiki Agent（wiki_agent/agent/graph.py），但生产评估并行走 evaluate_parallel。 首要读 app/graphs/evaluation_graph.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。

## 代码依据

- `app/graphs/evaluation_graph.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- 真并行 State 改造：用 Annotated reducer 或子 state 分片再 aggregate
- 代码入口：app/graphs/evaluation_graph.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「真并行 State 改造」最先看哪段代码？**

A: 打开 app/graphs/evaluation_graph.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 真并行 State 改造？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q044](../answers/Q044-State合并冲突.md)
- [Q046](../answers/Q046-Wiki-Agent节点.md)
