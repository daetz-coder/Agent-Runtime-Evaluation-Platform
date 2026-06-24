# Q76: Tactical 评估「除 plan 外所有 action」——为什么排除 plan？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q076 |
| 分类 | 六维评估器深入 |
| 难度 | ★ |

## 问题

Tactical 评估「除 plan 外所有 action」——为什么排除 plan？

## 参考答案

围绕 Tactical 排除 plan：plan 已在 Planning 维；Tactical 评执行步 relevance/efficiency/correctness 面试回答应先说业务场景，再落到 app/evaluators/tactical_evaluator.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。

## 代码依据

- `app/evaluators/tactical_evaluator.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- Tactical 排除 plan：plan 已在 Planning 维
- 代码入口：app/evaluators/tactical_evaluator.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「Tactical 排除 plan」最先看哪段代码？**

A: 打开 app/evaluators/tactical_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 Tactical 排除 plan？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q075](../answers/Q075-granularity定义.md)
- [Q077](../answers/Q077-Tactical例子.md)
