# Q47: `AsyncSqliteSaver` checkpoint 的作用是什么？会话恢复如何实现？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q047 |
| 分类 | LangGraph 与工作流编排 |
| 难度 | ★ |

## 问题

`AsyncSqliteSaver` checkpoint 的作用是什么？会话恢复如何实现？

## 参考答案

Q47 与 AsyncSqliteSaver 相关。checkpoint 持久化 thread_id；interrupt 后 ainvoke 恢复 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。LangGraph 同时服务评估 workflow（evaluation_graph.py）与 Wiki Agent（wiki_agent/agent/graph.py），但生产评估并行走 evaluate_parallel。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。

## 代码依据

- `app/wiki_agent/agent/graph.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- AsyncSqliteSaver：checkpoint 持久化 thread_id
- 代码入口：app/wiki_agent/agent/graph.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「AsyncSqliteSaver」最先看哪段代码？**

A: 打开 app/wiki_agent/agent/graph.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 AsyncSqliteSaver？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q046](../answers/Q046-Wiki-Agent节点.md)
- [Q048](../answers/Q048-decide-HITL.md)
