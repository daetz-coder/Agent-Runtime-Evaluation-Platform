# Q82: Memory 的 retention / relevance / consistency 如何定义？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q082 |
| 分类 | 六维评估器深入 |
| 难度 | ★ |

## 问题

Memory 的 retention / relevance / consistency 如何定义？

## 参考答案

围绕 Memory 三子维：retention/relevance/consistency 面试回答应先说业务场景，再落到 app/evaluators/memory_evaluator.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。

## 代码依据

- `app/evaluators/memory_evaluator.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- Memory 三子维：retention/relevance/consistency
- 代码入口：app/evaluators/memory_evaluator.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「Memory 三子维」最先看哪段代码？**

A: 打开 app/evaluators/memory_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 Memory 三子维？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q081](../answers/Q081-result-utilization.md)
- [Q083](../answers/Q083-key-facts可靠性.md)
