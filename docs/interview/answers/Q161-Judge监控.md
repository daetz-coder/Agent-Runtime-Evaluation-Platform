# Q161: 如何监控 Judge LLM 的 latency P99、error rate、token usage？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q161 |
| 分类 | 系统设计与生产化 |
| 难度 | ★ |

## 问题

如何监控 Judge LLM 的 latency P99、error rate、token usage？

## 参考答案

Q161 与 Judge 监控 相关。记录 latency/token metrics Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。当前 BackgroundTasks 适合 Demo 量级；10 万/日需 Celery、PostgreSQL、Judge 限流与多租户 workspace。若涉及接入，说明 sdk/adapters/ 三种 adapter 的场景选择。

## 代码依据

- `app/evaluators/base.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- Judge 监控：记录 latency/token metrics
- 代码入口：app/evaluators/base.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「Judge 监控」最先看哪段代码？**

A: 打开 app/evaluators/base.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 Judge 监控？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q160](../answers/Q160-平台观测.md)
- [Q162](../answers/Q162-Planning低分排查.md)
