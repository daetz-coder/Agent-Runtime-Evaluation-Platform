# Q192: 有没有遇到过 Judge LLM 和人工评分严重不一致的情况？怎么处理的？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q192 |
| 分类 | 开放讨论与行为面 |
| 难度 | ★ |

## 问题

有没有遇到过 Judge LLM 和人工评分严重不一致的情况？怎么处理的？

## 参考答案

问题「有没有遇到过 Judge LLM 和人工评分严重不一致的情况？怎么处理的？」考察 Judge 人工不一致。校准 prompt 或换 Judge 回答应落到本项目 trade-off：轨迹驱动、LLM Judge 校准、单调性回归门禁，而非纯概念。 首要读 app/evaluators/consensus.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。

## 代码依据

- `app/evaluators/consensus.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- Judge 人工不一致：校准 prompt 或换 Judge
- 代码入口：app/evaluators/consensus.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 如何结合本项目回答开放题？**

A: 引用 app/evaluators/consensus.py 与 evaluation_graph.py，讲清轨迹驱动评估价值。

**Q: 怎样体现架构深度？**

A: 对比 LangSmith 类观测工具，强调六维 rubric 与 monotonicity 校准。

**Q: 若 PM 要单一 KPI？**

A: 给 overall+六维雷达+recommendations，拒绝只看一个数。

## 相关题目

- [Q191](../answers/Q191-个人负责模块.md)
- [Q193](../answers/Q193-架构重做.md)
