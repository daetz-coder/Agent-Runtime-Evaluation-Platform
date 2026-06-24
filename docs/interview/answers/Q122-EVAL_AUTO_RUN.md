# Q122: `EVAL_AUTO_RUN` 如何在 Wiki 对话结束后自动触发评估？异步链路是什么？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q122 |
| 分类 | Wiki Agent 端到端实现 |
| 难度 | ★ |

## 问题

`EVAL_AUTO_RUN` 如何在 Wiki 对话结束后自动触发评估？异步链路是什么？

## 参考答案

Q122 与 EVAL_AUTO_RUN 相关。finish 后异步 POST /evaluations Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。Wiki 是 reference Agent：graph 节点 + EvaluationTrace 显式埋点 + EVAL_AUTO_RUN 自动评估。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。

## 代码依据

- `app/wiki_agent/evaluation.py`
- `app/core/config.py`
- `app/graphs/evaluation_graph.py`

## 回答要点

- EVAL_AUTO_RUN：finish 后异步 POST /evaluations
- 代码入口：app/wiki_agent/evaluation.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「EVAL_AUTO_RUN」最先看哪段代码？**

A: 打开 app/wiki_agent/evaluation.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 EVAL_AUTO_RUN？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q121](../answers/Q121-EvaluationTrace.md)
- [Q123](../answers/Q123-零侵入SDK.md)
