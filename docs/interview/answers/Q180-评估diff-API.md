# Q180: 实现一个简单的「评估结果 diff」API：对比同一 task 两次评估的六维分数变化。

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q180 |
| 分类 | 编码与现场设计题 |
| 难度 | ★ |

## 问题

实现一个简单的「评估结果 diff」API：对比同一 task 两次评估的六维分数变化。

## 参考答案

问题「实现一个简单的「评估结果 diff」API：对比同一 task 两次评估的六维分数变化。」考察 评估 diff API。对比两次 Evaluation ORM 记录 改动 Evaluator 需同步 app/models/schemas.py、evaluators/__init__.py、evaluation_graph 注册与 aggregate WEIGHTS。 首要读 app/api/v1/endpoints/evaluation.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。

## 代码依据

- `app/api/v1/endpoints/evaluation.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- 评估 diff API：对比两次 Evaluation ORM 记录
- 代码入口：app/api/v1/endpoints/evaluation.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「评估 diff API」最先看哪段代码？**

A: 打开 app/api/v1/endpoints/evaluation.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 评估 diff API？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q179](../answers/Q179-可执行性子维.md)
- [Q181](../answers/Q181-评估流水线2.0.md)
