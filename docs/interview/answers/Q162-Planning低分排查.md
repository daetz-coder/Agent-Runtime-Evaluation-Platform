# Q162: 用户反馈「Planning 分数总是很低」，你的排查步骤是什么？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q162 |
| 分类 | 调试、排错与案例分析 |
| 难度 | ★★ |

## 问题

用户反馈「Planning 分数总是很低」，你的排查步骤是什么？

## 参考答案

问题「用户反馈「Planning 分数总是很低」，你的排查步骤是什么？」考察 Planning 低分排查。查是否有 plan 动作；prompt feedback 排错顺序：轨迹完整性 → 单维 feedback → benchmark dim_scores 逆序定位 Evaluator。 首要读 app/evaluators/planning_evaluator.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。

## 代码依据

- `app/evaluators/planning_evaluator.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- Planning 低分排查：查是否有 plan 动作
- 代码入口：app/evaluators/planning_evaluator.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「Planning 低分排查」最先看哪段代码？**

A: 打开 app/evaluators/planning_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 Planning 低分排查？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q161](../answers/Q161-Judge监控.md)
- [Q163](../answers/Q163-overall高分争议.md)
