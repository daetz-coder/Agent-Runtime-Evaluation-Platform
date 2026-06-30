# Q139: 评估 API `POST /evaluations` 返回 202 异步，客户端如何获取结果？轮询还是 SSE？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q139 |
| 分类 | 后端工程与 API 设计 |
| 难度 | ★★ |

## 问题

评估 API `POST /evaluations` 返回 202 异步，客户端如何获取结果？轮询还是 SSE？

## 参考答案

客户端有两种获取结果的方式：**轮询**和 **SSE 流式推送**，分别适用于不同场景。

**创建评估（202 Accepted）。** `POST /evaluations`（`evaluation.py:138-204`）接收评估请求后，在数据库中创建一条 `IN_PROGRESS` 状态的记录，随即返回 `202 Accepted` 和 `evaluation_id`。实际评估任务通过 Celery worker 或 `BackgroundTasks`（`evaluation.py:191`）异步执行，不阻塞 HTTP 请求。

**方式一：轮询。** 客户端拿到 `evaluation_id` 后，周期性调用 `GET /evaluations/{evaluation_id}`（`evaluation.py:583-601`）。当 `status` 变为 `COMPLETED` 时，响应体中包含完整的评估结果（各维度分数、总分、详细反馈）。轮询间隔通常建议 2-5 秒，适合前端场景或不方便维护长连接的客户端。

**方式二：SSE 流式推送。** 客户端调用 `POST /evaluations/stream`（`evaluation.py:698-960`），在请求体中传入 `task_id` 或 `evaluation_id`，服务端返回 `text/event-stream` 响应。`event_generator`（`evaluation.py:873-958`）生成三种事件类型：

1. **progress** 事件：每个评估维度完成后立即推送该维度的分数，客户端可实时显示进度。
2. **result** 事件：所有维度完成后推送最终的综合评估结果。
3. **done** 事件：标记流结束，客户端可安全关闭连接。

**SSE 的重放机制。** 如果客户端请求的评估已经完成（数据库中已有结果），SSE 端点会直接从数据库读取并以 result + done 事件重放，不会重新触发 LLM 调用。这保证了幂等性。

**流去重。** `try_claim_stream` 机制防止同一任务的多个客户端同时发起流式连接导致重复评估。只有第一个成功 claim 的连接会触发实际评估，后续连接等待结果后重放。

## 代码依据

- `app/api/v1/endpoints/evaluation.py:138-204` — `POST /evaluations` 创建评估返回 202
- `app/api/v1/endpoints/evaluation.py:191` — Celery/BackgroundTasks 异步分发
- `app/api/v1/endpoints/evaluation.py:698-960` — `POST /evaluations/stream` SSE 端点
- `app/api/v1/endpoints/evaluation.py:873-958` — `event_generator` SSE 事件生成器
- `app/api/v1/endpoints/evaluation.py:583-601` — `GET /evaluations/{id}` 轮询端点

## 回答要点

- POST 创建评估返回 202，实际执行异步化（Celery 或 BackgroundTasks）
- 两种获取方式：轮询（GET 单次查询）和 SSE（POST /stream 实时推送）
- SSE 三种事件：progress（逐维度推送）、result（最终结果）、done（流结束）
- 已完成的评估从数据库重放，不重复调用 LLM，保证幂等性
- `try_claim_stream` 机制防止同一任务的重复评估

## 常见追问

**Q: 为什么同时提供轮询和 SSE，不只用一种？**

A: 轮询实现简单，适合快速原型和不支持 SSE 的客户端（如某些移动端 SDK）。SSE 适合需要实时进度的 Web 前端，用户体验更好。两者共存是 API 设计中的常见模式，对应 FastAPI 的同步/异步两种使用范式。

**Q: SSE 连接断开后怎么恢复？**

A: 客户端重新调用 `POST /evaluations/stream` 传入同一个 `evaluation_id`。如果评估已完成，服务端直接重放结果；如果仍在进行中，客户端会从当前进度继续接收后续事件（各维度结果独立持久化到数据库，重连后从数据库恢复状态）。

**Q: Celery 和 BackgroundTasks 的选择逻辑是什么？**

A: 如果配置了 Celery broker（Redis），走 Celery 异步队列，支持重试和并发控制；否则降级为 FastAPI 的 `BackgroundTasks`，适合单机部署。两者对客户端 API 表现一致。

## 相关题目

- [Q138](../answers/Q138-多模型benchmark.md)
- [Q140](../answers/Q140-SSE事件格式.md)
