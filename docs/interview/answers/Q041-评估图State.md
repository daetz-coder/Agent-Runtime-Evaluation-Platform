# Q41: LangGraph 评估图（`evaluation_graph.py`）的节点是如何定义的？State 里有哪些字段？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q041 |
| 分类 | LangGraph 与工作流编排 |
| 难度 | ★ |

## 问题

LangGraph 评估图（`evaluation_graph.py`）的节点是如何定义的？State 里有哪些字段？

## 参考答案

Q41 与 EvaluationState 相关。task_id/goal/trajectory/context + 六 score 字段 + overall_evaluation Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。LangGraph 同时服务评估 workflow（evaluation_graph.py）与 Wiki Agent（wiki_agent/agent/graph.py），但生产评估并行走 evaluate_parallel。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。

## 代码依据

- `app/graphs/evaluation_graph.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- EvaluationState：task_id/goal/trajectory/context + 六 score 字段 + overall_evaluation
- 代码入口：app/graphs/evaluation_graph.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「EvaluationState」最先看哪段代码？**

A: 打开 app/graphs/evaluation_graph.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 EvaluationState？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q040](../answers/Q040-评估工作流.md)
- [Q042](../answers/Q042-串行图与并行gather.md)
