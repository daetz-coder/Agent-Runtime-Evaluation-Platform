# Q92: 没有 retrieval 动作时得 0 分——对非 RAG Agent 是否公平？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q092 |
| 分类 | 六维评估器深入 |
| 难度 | ★ |

## 问题

没有 retrieval 动作时得 0 分——对非 RAG Agent 是否公平？

## 参考答案

Q92 与 无 retrieval 零分 相关。非 RAG Agent 该维 0；overall 仍加权需解读 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。

## 代码依据

- `app/evaluators/retrieval_evaluator.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- 无 retrieval 零分：非 RAG Agent 该维 0
- 代码入口：app/evaluators/retrieval_evaluator.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「无 retrieval 零分」最先看哪段代码？**

A: 打开 app/evaluators/retrieval_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 无 retrieval 零分？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q091](../answers/Q091-retrieved-docs结构.md)
- [Q093](../answers/Q093-幻觉评估.md)
