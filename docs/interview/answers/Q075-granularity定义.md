# Q75: 「计划粒度（granularity）」如何在 prompt 里定义？过细和过粗的计划如何区分？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q075 |
| 分类 | 六维评估器深入 |
| 难度 | ★ |

## 问题

「计划粒度（granularity）」如何在 prompt 里定义？过细和过粗的计划如何区分？

## 参考答案

问题「「计划粒度（granularity）」如何在 prompt 里定义？过细和过粗的计划如何区分？」考察 granularity。prompt 定义里程碑粒度适中；过细过粗 Judge 描述 每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。 首要读 app/evaluators/planning_evaluator.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。

## 代码依据

- `app/evaluators/planning_evaluator.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- granularity：prompt 定义里程碑粒度适中
- 代码入口：app/evaluators/planning_evaluator.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「granularity」最先看哪段代码？**

A: 打开 app/evaluators/planning_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 granularity？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q074](../answers/Q074-无plan零分.md)
- [Q076](../answers/Q076-Tactical排除plan.md)
