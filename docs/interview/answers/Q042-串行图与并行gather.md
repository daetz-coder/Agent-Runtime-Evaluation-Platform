# Q42: 代码注释写「LangGraph 并行评估」，但实际图是串行的；生产环境却用 `asyncio.gather` 并行。请解释这个「双路径」设计的原因。

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q042 |
| 分类 | LangGraph 与工作流编排 |
| 难度 | ★★★ |

## 问题

代码注释写「LangGraph 并行评估」，但实际图是串行的；生产环境却用 `asyncio.gather` 并行。请解释这个「双路径」设计的原因。

## 参考答案

问题「代码注释写「LangGraph 并行评估」，但实际图是串行的；生产环境却用 `asyncio.gather` 并行。请解释这个「双路径」设计的原因。」考察 双路径并行。图串行避 state merge；evaluate_parallel 用 asyncio.gather 71s→15s LangGraph 同时服务评估 workflow（evaluation_graph.py）与 Wiki Agent（wiki_agent/agent/graph.py），但生产评估并行走 evaluate_parallel。 首要读 app/graphs/evaluation_graph.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。

## 代码依据

- `app/graphs/evaluation_graph.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- 双路径并行：图串行避 state merge
- 代码入口：app/graphs/evaluation_graph.py
- LangGraph 图串行因 state merge
- evaluate_parallel 用 asyncio.gather
- 注释写明 71s→~15s

## 常见追问

**Q: 「双路径并行」最先看哪段代码？**

A: 打开 app/graphs/evaluation_graph.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 双路径并行？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q041](../answers/Q041-评估图State.md)
- [Q043](../answers/Q043-EVAL_PARALLEL切换.md)
