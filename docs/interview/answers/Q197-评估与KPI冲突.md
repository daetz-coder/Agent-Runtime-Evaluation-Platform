# Q197: 评估标准和业务 KPI 冲突时（例如评估高分但用户满意度低），如何对齐？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q197 |
| 分类 | 开放讨论与行为面 |
| 难度 | ★ |

## 问题

评估标准和业务 KPI 冲突时（例如评估高分但用户满意度低），如何对齐？

## 参考答案

Q197 与 评估与 KPI 相关。联合 dashboard 业务指标 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。回答应落到本项目 trade-off：轨迹驱动、LLM Judge 校准、单调性回归门禁，而非纯概念。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。

## 代码依据

- `app/graphs/evaluation_graph.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- 评估与 KPI：联合 dashboard 业务指标
- 代码入口：app/graphs/evaluation_graph.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 如何结合本项目回答开放题？**

A: 引用 app/graphs/evaluation_graph.py 与 evaluation_graph.py，讲清轨迹驱动评估价值。

**Q: 怎样体现架构深度？**

A: 对比 LangSmith 类观测工具，强调六维 rubric 与 monotonicity 校准。

**Q: 若 PM 要单一 KPI？**

A: 给 overall+六维雷达+recommendations，拒绝只看一个数。

## 相关题目

- [Q196](../answers/Q196-推广轨迹规范.md)
- [Q198](../answers/Q198-CI-benchmark.md)
