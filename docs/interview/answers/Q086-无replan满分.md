# Q86: 没有 replan 事件时默认满分 100——请解释这个设计逻辑，是否合理？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q086 |
| 分类 | 六维评估器深入 |
| 难度 | ★★★ |

## 问题

没有 replan 事件时默认满分 100——请解释这个设计逻辑，是否合理？

## 参考答案

Q86 与 无 replan 满分 相关。无 replan 且无 missed_opportunities 返回 100 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。若涉及接入，说明 sdk/adapters/ 三种 adapter 的场景选择。

## 代码依据

- `app/evaluators/replan_evaluator.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- 无 replan 满分：无 replan 且无 missed_opportunities 返回 100
- 代码入口：app/evaluators/replan_evaluator.py
- 无 replan 且无 missed→100 分
- _detect_missed_replans 连续 5 failure
- 有 missed 才走 LLM Judge

## 常见追问

**Q: 「无 replan 满分」最先看哪段代码？**

A: 打开 app/evaluators/replan_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 无 replan 满分？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q085](../answers/Q085-长短期记忆.md)
- [Q087](../answers/Q087-trigger-appropriateness.md)
