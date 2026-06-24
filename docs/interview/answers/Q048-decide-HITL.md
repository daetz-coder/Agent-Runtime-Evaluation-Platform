# Q48: Wiki Agent 的 `decide` 节点如何判断是否需要 human-in-the-loop？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q048 |
| 分类 | LangGraph 与工作流编排 |
| 难度 | ★ |

## 问题

Wiki Agent 的 `decide` 节点如何判断是否需要 human-in-the-loop？

## 参考答案

问题「Wiki Agent 的 `decide` 节点如何判断是否需要 human-in-the-loop？」考察 decide HITL。判断 extraction 等需人工确认的分支 LangGraph 同时服务评估 workflow（evaluation_graph.py）与 Wiki Agent（wiki_agent/agent/graph.py），但生产评估并行走 evaluate_parallel。 首要读 app/wiki_agent/agent/graph.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。

## 代码依据

- `app/wiki_agent/agent/graph.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- decide HITL：判断 extraction 等需人工确认的分支
- 代码入口：app/wiki_agent/agent/graph.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「decide HITL」最先看哪段代码？**

A: 打开 app/wiki_agent/agent/graph.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 decide HITL？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q047](../answers/Q047-AsyncSqliteSaver.md)
- [Q049](../answers/Q049-知识提取流程.md)
