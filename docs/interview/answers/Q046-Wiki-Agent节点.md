# Q46: Wiki Agent 的 LangGraph 图有哪些节点？`search → respond → decide → execute` 各自职责是什么？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q046 |
| 分类 | LangGraph 与工作流编排 |
| 难度 | ★ |

## 问题

Wiki Agent 的 LangGraph 图有哪些节点？`search → respond → decide → execute` 各自职责是什么？

## 参考答案

围绕 Wiki 节点：search 检索；respond 生成；decide HITL；execute 工具/提取 面试回答应先说业务场景，再落到 app/wiki_agent/agent/graph.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。LangGraph 同时服务评估 workflow（evaluation_graph.py）与 Wiki Agent（wiki_agent/agent/graph.py），但生产评估并行走 evaluate_parallel。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。

## 代码依据

- `app/wiki_agent/agent/graph.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- Wiki 节点：search 检索
- 代码入口：app/wiki_agent/agent/graph.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「Wiki 节点」最先看哪段代码？**

A: 打开 app/wiki_agent/agent/graph.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 Wiki 节点？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q045](../answers/Q045-真并行State改造.md)
- [Q047](../answers/Q047-AsyncSqliteSaver.md)
