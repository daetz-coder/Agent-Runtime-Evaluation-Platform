# Q53: LangGraph 的 `interrupt` 机制原理是什么？和 Celery 任务暂停有什么区别？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q053 |
| 分类 | LangGraph 与工作流编排 |
| 难度 | ★ |

## 问题

LangGraph 的 `interrupt` 机制原理是什么？和 Celery 任务暂停有什么区别？

## 参考答案

Q53 与 interrupt 相关。LangGraph interrupt 协作式暂停；非 Celery 抢占 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。LangGraph 同时服务评估 workflow（evaluation_graph.py）与 Wiki Agent（wiki_agent/agent/graph.py），但生产评估并行走 evaluate_parallel。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。

## 代码依据

- `app/wiki_agent/agent/graph.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- interrupt：LangGraph interrupt 协作式暂停
- 代码入口：app/wiki_agent/agent/graph.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「interrupt」最先看哪段代码？**

A: 打开 app/wiki_agent/agent/graph.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 interrupt？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q052](../answers/Q052-Subgraph.md)
- [Q054](../answers/Q054-LLM-as-Judge.md)
