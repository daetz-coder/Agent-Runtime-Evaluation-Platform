# Q55: 为什么所有 Evaluator 都设 `temperature=0`？如果改成 0.7 会怎样？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q055 |
| 分类 | LLM-as-Judge 评估体系 |
| 难度 | ★ |

## 问题

为什么所有 Evaluator 都设 `temperature=0`？如果改成 0.7 会怎样？

## 参考答案

围绕 temperature=0：降低 Judge 随机性；0.7 会导致同 trajectory 分波动大 面试回答应先说业务场景，再落到 app/evaluators/base.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。六维 Evaluator 继承 BaseEvaluator，temperature=0，JSON 解析失败时各子维 fallback 50 分。若涉及接入，说明 sdk/adapters/ 三种 adapter 的场景选择。

## 代码依据

- `app/evaluators/base.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- temperature=0：降低 Judge 随机性
- 代码入口：app/evaluators/base.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「temperature=0」最先看哪段代码？**

A: 打开 app/evaluators/base.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 temperature=0？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q054](../answers/Q054-LLM-as-Judge.md)
- [Q056](../answers/Q056-自评偏见.md)
