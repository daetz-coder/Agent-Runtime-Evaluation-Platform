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

>我选择 **FastAPI + Async SQLAlchemy** 的核心原因是这个项目本质上是一个 Agent Runtime Evaluation Engine，而不是传统的 CRUD Web 系统。系统需要同时处理 LLM 调用、RAG 检索、六个 Evaluator 并行执行以及 SSE 流式返回评估进度，这些都属于 IO 密集型场景，因此需要 async-first 架构。
>
>FastAPI 原生支持 async/await，可以通过 `asyncio.gather` 并行执行多个评估器；同时支持 SSE 流式接口，适合实时展示评估进度。Pydantic 提供强类型 Schema，使 Trajectory、EvaluationRequest、EvaluationResult 等对象能够自动校验、序列化并生成 OpenAPI 文档。
>
>数据层选择 Async SQLAlchemy，是为了让数据库 IO 与 LLM 调用都采用非阻塞方式，避免评估过程中出现同步阻塞。
>
>相比之下，Django 更偏重传统 MVC 和后台管理系统，框架较重；Flask 虽然轻量，但异步能力、类型系统和自动文档支持不如 FastAPI。因此 FastAPI + Async SQLAlchemy 更符合 Agent 评估平台这种高并发、流式、异步的架构需求。
>
>FastAPI 的一个重要优势就是强类型接口。它基于 Python Type Hints 和 Pydantic Schema，对请求和响应进行自动校验和序列化。例如 EvaluationRequest、Trajectory、EvaluationResult 都可以定义成 Pydantic 模型，FastAPI 会自动检查字段类型、生成 OpenAPI 文档，并保证接口输入输出符合预期。相比 Flask 这种依赖手工解析 JSON 的方式，类型安全性和可维护性都更好，尤其适合我们这种包含大量 Trajectory 和 Evaluation 数据结构的 Agent 平台。



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
