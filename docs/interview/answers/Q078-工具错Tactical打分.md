# Q78: 如果 Agent 做了正确决策但工具返回错误导致失败，Tactical 应该怎么打分？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q078 |
| 分类 | 六维评估器深入 |
| 难度 | ★ |

## 问题

如果 Agent 做了正确决策但工具返回错误导致失败，Tactical 应该怎么打分？

## 参考答案

问题「如果 Agent 做了正确决策但工具返回错误导致失败，Tactical 应该怎么打分？」考察 工具错 Tactical。决策正确但工具失败：correctness 考虑决策非环境 每维 Evaluator 有独立 prompt 与子维权重，overall 在 aggregate_results 再按 20/20/15/15/15/15 汇总。 首要读 app/evaluators/tactical_evaluator.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。

## 代码依据

- `app/evaluators/tactical_evaluator.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- 工具错 Tactical：决策正确但工具失败：correctness 考虑决策非环境
- 代码入口：app/evaluators/tactical_evaluator.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「工具错 Tactical」最先看哪段代码？**

A: 打开 app/evaluators/tactical_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 工具错 Tactical？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q077](../answers/Q077-Tactical例子.md)
- [Q079](../answers/Q079-ToolUse三子维.md)
