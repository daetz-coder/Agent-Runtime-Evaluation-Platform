# Q62: 各 Evaluator 的 prompt 是中文还是英文？对 Judge 质量有什么影响？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q062 |
| 分类 | LLM-as-Judge 评估体系 |
| 难度 | ★ |

## 问题

各 Evaluator 的 prompt 是中文还是英文？对 Judge 质量有什么影响？

## 参考答案

Q62 与 中英文 prompt 相关。当前英文 prompt；中文 trajectory 可能略降 Judge 质量 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。六维 Evaluator 继承 BaseEvaluator，temperature=0，JSON 解析失败时各子维 fallback 50 分。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。

## 代码依据

- `app/evaluators/planning_evaluator.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- 中英文 prompt：当前英文 prompt
- 代码入口：app/evaluators/planning_evaluator.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「中英文 prompt」最先看哪段代码？**

A: 打开 app/evaluators/planning_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 中英文 prompt？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q061](../answers/Q061-Planning-prompt.md)
- [Q063](../answers/Q063-few-shot.md)
