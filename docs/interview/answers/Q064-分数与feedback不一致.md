# Q64: 如果 Judge 给出的 feedback 和 score 不一致（高分但 feedback 全是批评），如何处理？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q064 |
| 分类 | LLM-as-Judge 评估体系 |
| 难度 | ★ |

## 问题

如果 Judge 给出的 feedback 和 score 不一致（高分但 feedback 全是批评），如何处理？

## 参考答案

围绕 分数 feedback 不一致：后处理校验或让 Judge 输出 reasoning chain 面试回答应先说业务场景，再落到 app/evaluators/planning_evaluator.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。六维 Evaluator 继承 BaseEvaluator，temperature=0，JSON 解析失败时各子维 fallback 50 分。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。

## 代码依据

- `app/evaluators/planning_evaluator.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- 分数 feedback 不一致：后处理校验或让 Judge 输出 reasoning chain
- 代码入口：app/evaluators/planning_evaluator.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「分数 feedback 不一致」最先看哪段代码？**

A: 打开 app/evaluators/planning_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 分数 feedback 不一致？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q063](../answers/Q063-few-shot.md)
- [Q065](../answers/Q065-Prompt-Injection.md)
