# Q94: coverage 低但 relevance 高，说明什么问题？如何给 Agent 开发者 actionable 的建议？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q094 |
| 分类 | 六维评估器深入 |
| 难度 | ★ |

## 问题

coverage 低但 relevance 高，说明什么问题？如何给 Agent 开发者 actionable 的建议？

## 参考答案

围绕 coverage 低：召回窄；建议扩大 query 或 hybrid top_k 面试回答应先说业务场景，再落到 app/evaluators/retrieval_evaluator.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。

## 代码依据

- `app/evaluators/retrieval_evaluator.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- coverage 低：召回窄
- 代码入口：app/evaluators/retrieval_evaluator.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「coverage 低」最先看哪段代码？**

A: 打开 app/evaluators/retrieval_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 coverage 低？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q093](../answers/Q093-幻觉评估.md)
- [Q095](../answers/Q095-六维overall权重.md)
