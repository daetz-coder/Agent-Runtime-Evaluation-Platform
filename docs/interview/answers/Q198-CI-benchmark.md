# Q198: 如何在 CI/CD 里集成单调性 benchmark 作为 merge gate？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q198 |
| 分类 | 开放讨论与行为面 |
| 难度 | ★ |

## 问题

如何在 CI/CD 里集成单调性 benchmark 作为 merge gate？

## 参考答案

问题「如何在 CI/CD 里集成单调性 benchmark 作为 merge gate？」考察 CI benchmark。pytest merge gate 回答应落到本项目 trade-off：轨迹驱动、LLM Judge 校准、单调性回归门禁，而非纯概念。 首要读 app/benchmarks/monotonicity.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。

## 代码依据

- `app/benchmarks/monotonicity.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- CI benchmark：pytest merge gate
- 代码入口：app/benchmarks/monotonicity.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 如何结合本项目回答开放题？**

A: 引用 app/benchmarks/monotonicity.py 与 evaluation_graph.py，讲清轨迹驱动评估价值。

**Q: 怎样体现架构深度？**

A: 对比 LangSmith 类观测工具，强调六维 rubric 与 monotonicity 校准。

**Q: 若 PM 要单一 KPI？**

A: 给 overall+六维雷达+recommendations，拒绝只看一个数。

## 相关题目

- [Q197](../answers/Q197-评估与KPI冲突.md)
- [Q199](../answers/Q199-领域专家协作.md)
