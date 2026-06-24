# Q52: Subgraph 和 parent graph 如何共享状态？有没有考虑过把 Wiki Agent 拆成 subgraph？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q052 |
| 分类 | LangGraph 与工作流编排 |
| 难度 | ★ |

## 问题

Subgraph 和 parent graph 如何共享状态？有没有考虑过把 Wiki Agent 拆成 subgraph？

## 参考答案

围绕 Subgraph：可拆 search 为 subgraph 共享 state keys 面试回答应先说业务场景，再落到 app/wiki_agent/agent/graph.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。LangGraph 同时服务评估 workflow（evaluation_graph.py）与 Wiki Agent（wiki_agent/agent/graph.py），但生产评估并行走 evaluate_parallel。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。

## 代码依据

- `app/wiki_agent/agent/graph.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- Subgraph：可拆 search 为 subgraph 共享 state keys
- 代码入口：app/wiki_agent/agent/graph.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「Subgraph」最先看哪段代码？**

A: 打开 app/wiki_agent/agent/graph.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 Subgraph？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q051](../answers/Q051-条件边.md)
- [Q053](../answers/Q053-interrupt机制.md)
