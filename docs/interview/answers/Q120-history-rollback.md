# Q120: Git 风格的 history / rollback 是如何实现的？回滚后索引如何恢复？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q120 |
| 分类 | Wiki Agent 端到端实现 |
| 难度 | ★ |

## 问题

Git 风格的 history / rollback 是如何实现的？回滚后索引如何恢复？

## 参考答案

问题「Git 风格的 history / rollback 是如何实现的？回滚后索引如何恢复？」考察 history rollback。版本链+回滚触发 reindex Wiki 是 reference Agent：graph 节点 + EvaluationTrace 显式埋点 + EVAL_AUTO_RUN 自动评估。 首要读 app/wiki_agent/，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及分数聚合，说明 planning/tactical 权重 20%，其余四维各 15%，见 aggregate_results。

## 代码依据

- `app/wiki_agent/`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- history rollback：版本链+回滚触发 reindex
- 代码入口：app/wiki_agent/
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「history rollback」最先看哪段代码？**

A: 打开 app/wiki_agent/，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 history rollback？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q119](../answers/Q119-CRUD索引同步.md)
- [Q121](../answers/Q121-EvaluationTrace.md)
