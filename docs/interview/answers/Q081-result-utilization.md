# Q81: 工具返回结果被 Agent 忽略（result_utilization 低），在实际 Agent 里常见吗？如何检测？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q081 |
| 分类 | 六维评估器深入 |
| 难度 | ★ |

## 问题

工具返回结果被 Agent 忽略（result_utilization 低），在实际 Agent 里常见吗？如何检测？

## 参考答案

问题「工具返回结果被 Agent 忽略（result_utilization 低），在实际 Agent 里常见吗？如何检测？」考察 result_utilization。常见忽略 tool_result；检测 action 是否引用 result 每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。 首要读 app/evaluators/tool_use_evaluator.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。

## 代码依据

- `app/evaluators/tool_use_evaluator.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- result_utilization：常见忽略 tool_result
- 代码入口：app/evaluators/tool_use_evaluator.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「result_utilization」最先看哪段代码？**

A: 打开 app/evaluators/tool_use_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 result_utilization？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q080](../answers/Q080-参数JSON错误.md)
- [Q082](../answers/Q082-Memory三子维.md)
