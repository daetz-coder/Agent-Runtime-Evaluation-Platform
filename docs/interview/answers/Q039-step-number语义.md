# Q39: 轨迹 step_number 的语义是什么？乱序上报如何处理？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q039 |
| 分类 | 轨迹（Trajectory）与埋点 |
| 难度 | ★ |

## 问题

轨迹 step_number 的语义是什么？乱序上报如何处理？

## 参考答案

问题「轨迹 step_number 的语义是什么？乱序上报如何处理？」考察 step_number。单调递增；乱序上报应服务端排序或拒绝 轨迹是六维 Judge 的唯一输入，ActionType 契约在 app/models/action_types.py 与 sdk/collector.py 双处维护。 首要读 sdk/collector.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。

## 代码依据

- `sdk/collector.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- step_number：单调递增
- 代码入口：sdk/collector.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「step_number」最先看哪段代码？**

A: 打开 sdk/collector.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 step_number？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q038](../answers/Q038-observation序列化.md)
- [Q040](../answers/Q040-评估工作流.md)
