# Q187: 你怎么看 Multi-Agent 评估？本项目能否扩展到评估 Agent 团队协作？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q187 |
| 分类 | 开放讨论与行为面 |
| 难度 | ★ |

## 问题

你怎么看 Multi-Agent 评估？本项目能否扩展到评估 Agent 团队协作？

## 参考答案

围绕 Multi-Agent 评估：扩展 trajectory 含 agent_id 面试回答应先说业务场景，再落到 app/evaluators/ 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。回答应落到本项目 trade-off：轨迹驱动、LLM Judge 校准、单调性回归门禁，而非纯概念。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。

## 代码依据

- `app/evaluators/`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- Multi-Agent 评估：扩展 trajectory 含 agent_id
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

- [Q186](../answers/Q186-Agent趋势.md)
- [Q188](../answers/Q188-可解释与可评估.md)
