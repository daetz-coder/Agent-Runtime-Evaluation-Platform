# Q189: RLHF / DPO 训练的 Agent 和 prompt-based Agent，评估方法应该有什么不同？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q189 |
| 分类 | 开放讨论与行为面 |
| 难度 | ★ |

## 问题

RLHF / DPO 训练的 Agent 和 prompt-based Agent，评估方法应该有什么不同？

## 参考答案

问题「RLHF / DPO 训练的 Agent 和 prompt-based Agent，评估方法应该有什么不同？」考察 RLHF vs prompt。RLHF Agent 评 policy 一致性 回答应落到本项目 trade-off：轨迹驱动、LLM Judge 校准、单调性回归门禁，而非纯概念。 首要读 app/evaluators/，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。

## 代码依据

- `app/evaluators/`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- RLHF vs prompt：RLHF Agent 评 policy 一致性
- 代码入口：app/evaluators/
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 如何结合本项目回答开放题？**

A: 引用 app/evaluators/ 与 evaluation_graph.py，讲清轨迹驱动评估价值。

**Q: 怎样体现架构深度？**

A: 对比 LangSmith 类观测工具，强调六维 rubric 与 monotonicity 校准。

**Q: 若 PM 要单一 KPI？**

A: 给 overall+六维雷达+recommendations，拒绝只看一个数。

## 相关题目

- [Q188](../answers/Q188-可解释与可评估.md)
- [Q190](../answers/Q190-长上下文挑战.md)
