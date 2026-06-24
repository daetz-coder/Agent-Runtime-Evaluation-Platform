# Q95: 六维 overall 权重（planning 20%、tactical 20%、其余各 15%）是如何定的？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q095 |
| 分类 | 六维评估器深入 |
| 难度 | ★ |

## 问题

六维 overall 权重（planning 20%、tactical 20%、其余各 15%）是如何定的？

## 参考答案

Q95 与 overall 权重 相关。planning/tactical 0.2；其余 0.15 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。

## 代码依据

- `app/graphs/evaluation_graph.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- overall 权重：planning/tactical 0.2
- 代码入口：app/graphs/evaluation_graph.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「overall 权重」最先看哪段代码？**

A: 打开 app/graphs/evaluation_graph.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 overall 权重？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q094](../answers/Q094-coverage低建议.md)
- [Q096](../answers/Q096-两级加权.md)
