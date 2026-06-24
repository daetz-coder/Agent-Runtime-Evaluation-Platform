# Q116: `SYSTEM_PROMPT` 的核心约束是什么？如何减少幻觉？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q116 |
| 分类 | Wiki Agent 端到端实现 |
| 难度 | ★ |

## 问题

`SYSTEM_PROMPT` 的核心约束是什么？如何减少幻觉？

## 参考答案

Q116 与 SYSTEM_PROMPT 相关。约束引用来源、拒答无证据 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。Wiki 是 reference Agent：graph 节点 + EvaluationTrace 显式埋点 + EVAL_AUTO_RUN 自动评估。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。

## 代码依据

- `app/wiki_agent/agent/`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- SYSTEM_PROMPT：约束引用来源、拒答无证据
- 代码入口：app/wiki_agent/agent/
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「SYSTEM_PROMPT」最先看哪段代码？**

A: 打开 app/wiki_agent/agent/，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 SYSTEM_PROMPT？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q115](../answers/Q115-Chat-SSE.md)
- [Q117](../answers/Q117-自动提取.md)
