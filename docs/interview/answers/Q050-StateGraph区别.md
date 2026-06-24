# Q50: LangGraph 的 `StateGraph` 和 `CompiledStateGraph` 区别是什么？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q050 |
| 分类 | LangGraph 与工作流编排 |
| 难度 | ★★ |

## 问题

LangGraph 的 `StateGraph` 和 `CompiledStateGraph` 区别是什么？

## 参考答案

Q50 与 StateGraph vs Compiled 相关。StateGraph 构建；compile() 得可 invoke 图 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。LangGraph 同时服务评估 workflow（evaluation_graph.py）与 Wiki Agent（wiki_agent/agent/graph.py），但生产评估并行走 evaluate_parallel。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。

## 代码依据

- `app/graphs/evaluation_graph.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- StateGraph vs Compiled：StateGraph 构建
- 代码入口：app/graphs/evaluation_graph.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「StateGraph vs Compiled」最先看哪段代码？**

A: 打开 app/graphs/evaluation_graph.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 StateGraph vs Compiled？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q049](../answers/Q049-知识提取流程.md)
- [Q051](../answers/Q051-条件边.md)
