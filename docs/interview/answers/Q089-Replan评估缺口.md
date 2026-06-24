# Q89: 对比 OpenAI 的 replanning 论文或 industry best practice，本项目的 Replan 评估缺什么？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q089 |
| 分类 | 六维评估器深入 |
| 难度 | ★ |

## 问题

对比 OpenAI 的 replanning 论文或 industry best practice，本项目的 Replan 评估缺什么？

## 参考答案

Q89 与 Replan 缺口 相关。缺 plan diff 量化；可对标 industry replanning rubric Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。

## 代码依据

- `app/evaluators/replan_evaluator.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- Replan 缺口：缺 plan diff 量化
- 代码入口：app/evaluators/replan_evaluator.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「Replan 缺口」最先看哪段代码？**

A: 打开 app/evaluators/replan_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 Replan 缺口？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q088](../answers/Q088-failure与replan.md)
- [Q090](../answers/Q090-Retrieval三子维.md)
