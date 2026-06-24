# Q72: Planning 的四个子维度（coverage、ordering、granularity、completeness）分别评估什么？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q072 |
| 分类 | 六维评估器深入 |
| 难度 | ★★ |

## 问题

Planning 的四个子维度（coverage、ordering、granularity、completeness）分别评估什么？

## 参考答案

问题「Planning 的四个子维度（coverage、ordering、granularity、completeness）分别评估什么？」考察 Planning 四子维。coverage/ordering/granularity/completeness 每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。 首要读 app/evaluators/planning_evaluator.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。

## 代码依据

- `app/evaluators/planning_evaluator.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- Planning 四子维：coverage/ordering/granularity/completeness
- 代码入口：app/evaluators/planning_evaluator.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「Planning 四子维」最先看哪段代码？**

A: 打开 app/evaluators/planning_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 Planning 四子维？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q071](../answers/Q071-部分维度复用.md)
- [Q073](../answers/Q073-Planning权重.md)
