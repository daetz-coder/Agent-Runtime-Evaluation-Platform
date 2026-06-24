# Q44: LangGraph 状态合并（state merge）冲突是什么？为什么并行 evaluator 节点会导致冲突？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q044 |
| 分类 | LangGraph 与工作流编排 |
| 难度 | ★ |

## 问题

LangGraph 状态合并（state merge）冲突是什么？为什么并行 evaluator 节点会导致冲突？

## 参考答案

Q44 与 state merge 冲突 相关。并行节点写同一 state key 会覆盖；故串行边 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。LangGraph 同时服务评估 workflow（evaluation_graph.py）与 Wiki Agent（wiki_agent/agent/graph.py），但生产评估并行走 evaluate_parallel。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。

## 代码依据

- `app/graphs/evaluation_graph.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- state merge 冲突：并行节点写同一 state key 会覆盖
- 代码入口：app/graphs/evaluation_graph.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「state merge 冲突」最先看哪段代码？**

A: 打开 app/graphs/evaluation_graph.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 state merge 冲突？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q043](../answers/Q043-EVAL_PARALLEL切换.md)
- [Q045](../answers/Q045-真并行State改造.md)
