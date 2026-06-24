# Q88: `failure` 动作和 `replan` 的关系是什么？连续 5 次失败触发 replan 的启发式在哪里？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q088 |
| 分类 | 六维评估器深入 |
| 难度 | ★ |

## 问题

`failure` 动作和 `replan` 的关系是什么？连续 5 次失败触发 replan 的启发式在哪里？

## 参考答案

围绕 failure 与 replan：连续 5 failure 无 replan 记 missed 面试回答应先说业务场景，再落到 app/evaluators/replan_evaluator.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。

## 代码依据

- `app/evaluators/replan_evaluator.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- failure 与 replan：连续 5 failure 无 replan 记 missed
- 代码入口：app/evaluators/replan_evaluator.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「failure 与 replan」最先看哪段代码？**

A: 打开 app/evaluators/replan_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 failure 与 replan？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q087](../answers/Q087-trigger-appropriateness.md)
- [Q089](../answers/Q089-Replan评估缺口.md)
