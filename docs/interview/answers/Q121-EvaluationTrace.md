# Q121: Wiki Agent 的 `EvaluationTrace` 记录了哪些事件？与 SDK collector 上报格式是否一致？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q121 |
| 分类 | Wiki Agent 端到端实现 |
| 难度 | ★ |

## 问题

Wiki Agent 的 `EvaluationTrace` 记录了哪些事件？与 SDK collector 上报格式是否一致？

## 参考答案

围绕 EvaluationTrace 事件：plan/tool/retrieval 等与 SDK 同 schema 面试回答应先说业务场景，再落到 app/wiki_agent/evaluation.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。Wiki 是 reference Agent：graph 节点 + EvaluationTrace 显式埋点 + EVAL_AUTO_RUN 自动评估。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。

## 代码依据

- `app/wiki_agent/evaluation.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- EvaluationTrace 事件：plan/tool/retrieval 等与 SDK 同 schema
- 代码入口：app/wiki_agent/evaluation.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「EvaluationTrace 事件」最先看哪段代码？**

A: 打开 app/wiki_agent/evaluation.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 EvaluationTrace 事件？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q120](../answers/Q120-history-rollback.md)
- [Q122](../answers/Q122-EVAL_AUTO_RUN.md)
