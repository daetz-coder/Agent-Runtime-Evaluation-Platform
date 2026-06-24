# Q146: 可选 API Key 认证（`AUTH_ENABLED`）的实现方式？哪些路径跳过认证？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q146 |
| 分类 | 后端工程与 API 设计 |
| 难度 | ★ |

## 问题

可选 API Key 认证（`AUTH_ENABLED`）的实现方式？哪些路径跳过认证？

## 参考答案

Q146 与 AUTH_ENABLED 相关。API Key header；health 跳过 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。FastAPI 异步 + SQLAlchemy 2.0；POST /evaluations 返回 202，/evaluations/stream 提供 SSE progress。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。

## 代码依据

- `app/core/config.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- AUTH_ENABLED：API Key header
- 代码入口：app/core/config.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「AUTH_ENABLED」最先看哪段代码？**

A: 打开 app/core/config.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 AUTH_ENABLED？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q145](../answers/Q145-SQLite-PostgreSQL.md)
- [Q147](../answers/Q147-双health端点.md)
