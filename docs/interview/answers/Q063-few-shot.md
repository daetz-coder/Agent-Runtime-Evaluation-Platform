# Q63: 如何在 prompt 里注入 few-shot 示例？本项目有没有做？效果如何？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q063 |
| 分类 | LLM-as-Judge 评估体系 |
| 难度 | ★ |

## 问题

如何在 prompt 里注入 few-shot 示例？本项目有没有做？效果如何？

## 参考答案

问题「如何在 prompt 里注入 few-shot 示例？本项目有没有做？效果如何？」考察 few-shot。可在 prompt 加示例；本项目默认 zero-shot 六维 Evaluator 继承 BaseEvaluator，temperature=0，JSON 解析失败时各子维 fallback 50 分。 首要读 app/evaluators/planning_evaluator.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。

## 代码依据

- `app/evaluators/planning_evaluator.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- few-shot：可在 prompt 加示例
- 代码入口：app/evaluators/planning_evaluator.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「few-shot」最先看哪段代码？**

A: 打开 app/evaluators/planning_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 few-shot？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q062](../answers/Q062-中英文prompt.md)
- [Q064](../answers/Q064-分数与feedback不一致.md)
