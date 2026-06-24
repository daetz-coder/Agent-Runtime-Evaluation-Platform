# Q164: Retrieval 0 分但 Agent 明明做了 RAG——最可能的原因是什么？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q164 |
| 分类 | 调试、排错与案例分析 |
| 难度 | ★ |

## 问题

Retrieval 0 分但 Agent 明明做了 RAG——最可能的原因是什么？

## 参考答案

Q164 与 Retrieval 0 分 相关。最可能未 record_retrieval Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。排错顺序：轨迹完整性 → 单维 feedback → benchmark dim_scores 逆序定位 Evaluator。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。

## 代码依据

- `app/evaluators/retrieval_evaluator.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- Retrieval 0 分：最可能未 record_retrieval
- 代码入口：app/evaluators/retrieval_evaluator.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「Retrieval 0 分」最先看哪段代码？**

A: 打开 app/evaluators/retrieval_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 Retrieval 0 分？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q163](../answers/Q163-overall高分争议.md)
- [Q165](../answers/Q165-benchmark失败定位.md)
