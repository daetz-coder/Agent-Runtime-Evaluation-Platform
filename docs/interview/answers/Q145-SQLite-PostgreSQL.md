# Q145: SQLite 默认 + PostgreSQL 可选，迁移策略是什么？Alembic 用到什么程度？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q145 |
| 分类 | 后端工程与 API 设计 |
| 难度 | ★ |

## 问题

SQLite 默认 + PostgreSQL 可选，迁移策略是什么？Alembic 用到什么程度？

## 参考答案

围绕 SQLite PostgreSQL：DATABASE_URL 切换；Alembic 可选 面试回答应先说业务场景，再落到 app/core/config.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。FastAPI 异步 + SQLAlchemy 2.0；POST /evaluations 返回 202，/evaluations/stream 提供 SSE progress。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。

## 代码依据

- `app/core/config.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- SQLite PostgreSQL：DATABASE_URL 切换
- 代码入口：app/core/config.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「SQLite PostgreSQL」最先看哪段代码？**

A: 打开 app/core/config.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 SQLite PostgreSQL？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q144](../answers/Q144-async-session.md)
- [Q146](../answers/Q146-AUTH_ENABLED.md)
