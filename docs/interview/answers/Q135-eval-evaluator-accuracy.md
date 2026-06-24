# Q135: `eval_evaluator_accuracy.py` 的好/坏场景对比测试是如何设计的？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q135 |
| 分类 | Benchmark 与评估校准 |
| 难度 | ★ |

## 问题

`eval_evaluator_accuracy.py` 的好/坏场景对比测试是如何设计的？

## 参考答案

问题「`eval_evaluator_accuracy.py` 的好/坏场景对比测试是如何设计的？」考察 eval_evaluator_accuracy。好/坏场景对比断言 monotonicity.py 六条合成轨迹，check_monotonicity 容差 +0.05，REFERENCE_SCORES 约 93.1→20.0。 首要读 tests/，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。

## 代码依据

- `tests/`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- eval_evaluator_accuracy：好/坏场景对比断言
- 代码入口：tests/
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「eval_evaluator_accuracy」最先看哪段代码？**

A: 打开 tests/，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 eval_evaluator_accuracy？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q134](../answers/Q134-逆序定位.md)
- [Q136](../answers/Q136-真实轨迹补充.md)
