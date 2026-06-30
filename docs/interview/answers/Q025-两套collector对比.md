# Q025: 请说明 `sdk/collector.py` 与 `app/collectors/inprocess_transport.py` 的关系：为什么 Wiki 内嵌时需要 in-process transport？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q025 |
| 分类 | 轨迹与埋点 |
| 难度 | ★★ |

## 问题

请说明 `sdk/collector.py` 与 `app/collectors/inprocess_transport.py` 的关系：为什么 Wiki 内嵌时需要 in-process transport？

## 参考答案

项目中存在两条轨迹传输路径：标准 HTTP 路径和 in-process 直写路径。两者的选择取决于 agent 是否与平台运行在同一个进程中。

**标准 HTTP 路径。** `sdk/collector.py` 中的 `TrajectoryCollector` 默认通过 HTTP 将轨迹发送到平台 API。在 `start` 方法（collector.py:244-281）中，collector 向 `{api_base}/api/v1/tasks/` 发送 POST 请求创建任务；在 `_flush` 方法（collector.py:756-778）中，collector 将缓冲的 steps 批量 POST 到 `/api/v1/tasks/{id}/trajectory/`。batch size 由环境变量 `EVAL_BATCH_SIZE` 控制，默认为 10。

**为什么需要 in-process。** Wiki Agent 运行在与平台相同的 FastAPI/uvicorn 进程中。如果 Wiki Agent 在处理聊天请求时通过 HTTP 调用 `localhost:8000`，会产生自我死锁——当前请求的协程阻塞在同步 HTTP 调用上，而目标 endpoint 需要同一个事件循环来处理。in-process transport 的模块注释（inprocess_transport.py:1-9）明确说明了这个问题。

**检测机制。** `collector.py:208-216` 的 `use_inprocess()` 方法检查 `EVAL_API_BASE_URL` 是否指向本机（`127.0.0.1` 或 `localhost`）。如果是且 `EVAL_INPROCESS=True`（默认值），则走 in-process 路径。

**in-process 直写路径。** `app/collectors/inprocess_transport.py` 提供三个核心函数：
1. `create_task_record`（line 27-46）：通过 `EvaluationService` 直接写 DB 创建任务，跳过 HTTP。
2. `persist_collector_session`（line 49-76）：在 `finish_async` 时被调用，将所有 buffered steps 一次性写入 DB、标记任务完成、可选触发评估。
3. `_run_evaluation_background`（line 79-108）：通过 `asyncio.create_task` fire-and-forget 启动评估，不阻塞聊天响应。

**关键差异：**
- HTTP 路径分批 flush（batch size=10），in-process 在 `finish_async` 时一次性写入所有 steps。
- HTTP 路径的 `_flush` 在 `use_inprocess()` 为 True 时直接 return（collector.py:757-758），不做任何 HTTP 调用。
- in-process 路径直接操作 SQLAlchemy async session，无网络开销。

## 代码依据

- `sdk/collector.py:208-216` — `use_inprocess()` 检测 API_BASE_URL 是否指向本机
- `sdk/collector.py:283-306` — `start_async` 在 inprocess 模式下调用 `create_task_record`
- `sdk/collector.py:337-361` — `finish_async` 在 inprocess 模式下调用 `persist_collector_session`
- `sdk/collector.py:756-778` — `_flush` 在 inprocess 模式下直接 return
- `app/collectors/inprocess_transport.py:27-46` — `create_task_record` 直接写 DB 创建任务
- `app/collectors/inprocess_transport.py:49-76` — `persist_collector_session` 一次性写入所有 steps
- `app/collectors/inprocess_transport.py:79-108` — `_run_evaluation_background` fire-and-forget 评估

## 回答要点

- 标准路径：collector 通过 HTTP POST 发送轨迹到平台 API，支持批量和重试
- in-process 路径：Wiki Agent 与平台同进程，HTTP 调用 localhost 会导致事件循环自我死锁
- `use_inprocess()` 检测 API_BASE_URL 是否指向 127.0.0.1/localhost
- in-process 直接通过 SQLAlchemy async session 写 DB，跳过 HTTP
- 关键差异：HTTP 分批 flush（batch=10），in-process 一次性写入

## 常见追问

**Q: 如果 Wiki Agent 部署在独立进程中，还需要 in-process transport 吗？**

A: 不需要。此时 `use_inprocess()` 返回 False，collector 会走标准 HTTP 路径。in-process transport 仅在 agent 与平台同进程时才激活。

**Q: `asyncio.create_task` 的 fire-and-forget 模式有什么风险？**

A: 如果评估抛异常，`_run_evaluation_background`（inprocess_transport.py:79-108）会捕获异常并调用 `abort_pending_evaluation` 标记评估失败。但如果进程在评估完成前退出，评估会停留在 pending 状态。这是可接受的 trade-off——优先保证聊天响应不被评估延迟阻塞。

## 相关题目

- [Q013](../answers/Q013-轨迹驱动评估.md)
- [Q030](../answers/Q030-低侵入埋点.md)
