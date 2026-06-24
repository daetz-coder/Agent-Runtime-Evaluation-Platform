# Q195: 从 0 到 1 搭建 Agent 系统，你会优先做评估平台还是优先做 Agent 本身？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q195 |
| 分类 | 开放讨论与行为面 |
| 难度 | ★ |

## 问题

从 0 到 1 搭建 Agent 系统，你会优先做评估平台还是优先做 Agent 本身？

## 参考答案

问题「从 0 到 1 搭建 Agent 系统，你会优先做评估平台还是优先做 Agent 本身？」考察 评估 vs Agent 优先。MVP 可 Demo Agent；规模化需 eval 先行 回答应落到本项目 trade-off：轨迹驱动、LLM Judge 校准、单调性回归门禁，而非纯概念。 首要读 app/，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。

## 代码依据

- `app/`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- 评估 vs Agent 优先：MVP 可 Demo Agent
- 代码入口：app/
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 如何结合本项目回答开放题？**

A: 引用 app/ 与 evaluation_graph.py，讲清轨迹驱动评估价值。

**Q: 怎样体现架构深度？**

A: 对比 LangSmith 类观测工具，强调六维 rubric 与 monotonicity 校准。

**Q: 若 PM 要单一 KPI？**

A: 给 overall+六维雷达+recommendations，拒绝只看一个数。

## 相关题目

- [Q194](../answers/Q194-技术债.md)
- [Q196](../answers/Q196-推广轨迹规范.md)
