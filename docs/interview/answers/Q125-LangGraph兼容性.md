# Q125: LangGraph adapter 包装后，原有的 `graph.compile()`、`graph.ainvoke()` 接口是否完全兼容？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q125 |
| 分类 | SDK 与零侵入接入 |
| 难度 | ★ |

## 问题

LangGraph adapter 包装后，原有的 `graph.compile()`、`graph.ainvoke()` 接口是否完全兼容？

## 参考答案

Q125 与 LangGraph 兼容 相关。compile/ainvoke API 不变 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。sdk/ 可独立使用，三种 adapter 映射框架事件到 14 种 ActionType，EVAL_BATCH_SIZE 控制批量 flush。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。

## 代码依据

- `sdk/adapters/langgraph.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- LangGraph 兼容：compile/ainvoke API 不变
- 代码入口：sdk/adapters/langgraph.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「LangGraph 兼容」最先看哪段代码？**

A: 打开 sdk/adapters/langgraph.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 LangGraph 兼容？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q124](../answers/Q124-adapter路径.md)
- [Q126](../answers/Q126-同步异步节点.md)
