# Q9: 为什么后端选 FastAPI + 异步 SQLAlchemy，而不是 Django / Flask？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q009 |
| 分类 | 项目理解与动机 |
| 难度 | ★ |

## 问题

为什么后端选 FastAPI + 异步 SQLAlchemy，而不是 Django / Flask？

## 参考答案

FastAPI 原生 async 与 SQLAlchemy 2.0 AsyncSession（Depends(get_db)）匹配：评估六维并行 asyncio.gather、SSE 流式 POST /evaluations/stream 需非阻塞 I/O。Pydantic schemas 在 app/models/schemas.py 与 endpoint 类型安全。Django 过重、Flask 异步生态弱。SQLite 默认 aiosqlite，可切 PostgreSQL asyncpg。lifespan 在 main.py 初始化 DB 与 Wiki bootstrap。

## 代码依据

- `app/main.py`
- `app/db/session.py`
- `app/api/v1/endpoints/evaluation.py`

## 回答要点

- async 全链路：DB + LLM + SSE
- Pydantic v2 请求/响应校验
- Depends(get_db) 管理 session 生命周期
- 比 Django 轻、比 Flask 现代 async 支持好

## 常见追问

**Q: SQLite 生产够用吗？**

A: 评估量小可；10 万/日需 PostgreSQL + 队列。

**Q: 为何 pydantic-settings？**

A: EVAL_PARALLEL 等环境变量 case-sensitive 统一配置。

## 相关题目

- [Q008](../answers/Q008-为何选LangGraph.md)
- [Q010](../answers/Q010-LLM选型与可比性.md)
