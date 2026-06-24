# Q165: 单调性 benchmark 失败，如何定位是数据问题还是 Evaluator bug？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q165 |
| 分类 | 调试、排错与案例分析 |
| 难度 | ★ |

## 问题

单调性 benchmark 失败，如何定位是数据问题还是 Evaluator bug？

## 参考答案

问题「单调性 benchmark 失败，如何定位是数据问题还是 Evaluator bug？」考察 benchmark 失败。数据 vs Evaluator：看 dim 逆序 排错顺序：轨迹完整性 → 单维 feedback → benchmark dim_scores 逆序定位 Evaluator。 首要读 app/benchmarks/monotonicity.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。

## 代码依据

- `app/benchmarks/monotonicity.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- benchmark 失败：数据 vs Evaluator：看 dim 逆序
- 代码入口：app/benchmarks/monotonicity.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「benchmark 失败」最先看哪段代码？**

A: 打开 app/benchmarks/monotonicity.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 benchmark 失败？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q164](../answers/Q164-Retrieval零分.md)
- [Q166](../answers/Q166-Wiki不引用知识库.md)
