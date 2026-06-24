# Q73: 权重 0.3/0.2/0.2/0.3 是如何确定的？能否用数据驱动调权？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q073 |
| 分类 | 六维评估器深入 |
| 难度 | ★ |

## 问题

权重 0.3/0.2/0.2/0.3 是如何确定的？能否用数据驱动调权？

## 参考答案

围绕 Planning 权重：0.3/0.2/0.2/0.3；可用 benchmark 网格搜索 面试回答应先说业务场景，再落到 app/evaluators/planning_evaluator.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。

## 代码依据

- `app/evaluators/planning_evaluator.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- Planning 权重：0.3/0.2/0.2/0.3
- 代码入口：app/evaluators/planning_evaluator.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「Planning 权重」最先看哪段代码？**

A: 打开 app/evaluators/planning_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 Planning 权重？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q072](../answers/Q072-Planning四子维.md)
- [Q074](../answers/Q074-无plan零分.md)
