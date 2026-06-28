# API Documentation

## Base URL

```
http://localhost:8000/api/v1
```

## Authentication

可选中。设置 `AUTH_ENABLED=true` 启用 API Key 认证，通过 `Authorization: Bearer <key>` 或 `?api_key=<key>` 传递。

## 接口限流

评估相关 POST 接口启用了基于 Redis 的滑动窗口限流（需 Redis 可用，不可用时自动跳过）：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `RATE_LIMIT_ENABLED` | `true` | 是否启用限流 |
| `RATE_LIMIT_EVAL_PER_MINUTE` | `10` | 每分钟每客户端最大请求数 |

**限流范围**: `POST /evaluations/`、`POST /evaluations/quick`、`POST /evaluations/batch`、`POST /evaluations/stream`、`POST /evaluations/consensus`

**超限响应** (HTTP 429):
```json
{
  "detail": "Too many requests. Please try again later.",
  "retry_after": 23
}
```

**响应头**: `Retry-After`、`X-RateLimit-Limit`、`X-RateLimit-Remaining`

**客户端标识**: 优先使用 API Key（前 9 字符），无 Key 时使用客户端 IP。

---

## Endpoints

### Tasks

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST /tasks/` | 创建任务 |
| `GET /tasks/` | 列出任务（支持 `?skip=&limit=`） |
| `GET /tasks/{id}` | 获取任务详情 |
| `PUT /tasks/{id}` | 更新任务（goal/context/status） |
| `GET /tasks/dashboard` | 仪表板统计（总数、状态分布、最近 5 条） |
| `POST /tasks/{id}/trajectory` | 上传轨迹步骤（批量 JSON 数组） |

### Evaluations

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST /evaluations/` | 创建并运行评估（`use_stream=true` 跳过后台任务） |
| `POST /evaluations/stream` | **SSE 流式评估** — 实时推送 6 维进度 |
| `POST /evaluations/quick` | 同步评估（阻塞，返回完整结果） |
| `POST /evaluations/batch` | 批量评估 `{"task_ids": [...]}` |
| `POST /evaluations/consensus` | 多模型共识评估（DeepSeek+GLM+Qwen） |
| `GET /evaluations/` | 列出评估（支持 `?skip=&limit=&status=`） |
| `GET /evaluations/{id}` | 获取评估详情（含 6 维分数+反馈+版本信息） |
| `DELETE /evaluations/{id}` | 删除评估记录 |
| `GET /evaluations/{id}/replay` | **Replay 调试器** — 每步 LLM 原始 prompt/response |
| `GET /evaluations/{id}/judge-raw[/{dim}]` | **Judge 透明度** — 原始 judge prompt/response |
| `GET /evaluations/diff` | **Trajectory 对比** — 两 evaluation 步骤级 diff |
| `POST /evaluations/incremental` | **增量评估** — 仅重算变化维度 |
| `GET /evaluations/regression/check` | **回归检测** — 自动发现分数退化 |

### Reports

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET /reports/summary` | 评估摘要（总评估数、六维均分、分布、问题洞察） |
| `GET /reports/trends` | 按日期分组的评估趋势（Dashboard 图表数据） |
| `GET /reports/tasks/{id}/history` | 某任务的所有评估历史 |
| `GET /reports/dimensions/{dim}` | 单维度统计（planning/tactical/tool_use/memory/replan/retrieval） |
| `GET /reports/compare/{task_id}` | 同任务多轮评估迭代对比（趋势+分数差） |
| `GET /reports/export/{task_id}` | 导出 Markdown 评估报告（下载） |

### Benchmark

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET /benchmark/monotonicity` | 单调性基准元数据（6 档参考分数） |
| `POST /benchmark/monotonicity/run` | **SSE 流式**实时运行单调性基准 |

### CLI / Makefile

```bash
# 开发常用命令（详见 Makefile）
make lint          # ruff 检查
make typecheck     # mypy 类型检查
make test          # 运行全部测试
make test-cov      # 带覆盖率的测试
make test-fast     # 快速测试（跳过 Milvus）
make golden        # 运行 Golden Test Suite
make check-ci      # 完整 CI 门禁
make check-regression BASE=<id> HEAD=<id>  # 回归检查
make run           # 启动后端
make run-dev       # 热重载后端
make db-upgrade    # 数据库迁移
```

### Workspaces（多租户）

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST /workspaces/` | 创建工作区（自动生成 API Key） |
| `GET /workspaces/` | 列出工作区 |
| `GET /workspaces/{id}` | 获取工作区详情 |
| `POST /workspaces/{id}/rotate-key` | 轮换 API Key |
| `POST /workspaces/{id}/members` | 添加成员（admin/evaluator/viewer） |
| `DELETE /workspaces/{id}/members/{uid}` | 移除成员 |
| `GET /workspaces/{id}/audit` | 审计日志 |

### Wiki Agent

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET /api/wiki/tree` | 知识库目录树 |
| `GET /api/wiki/page/{path}` | 获取页面内容 |
| `POST /api/wiki/create` | 创建页面（自动四路同步） |
| `PUT /api/wiki/update/{path}` | 更新页面 |
| `DELETE /api/wiki/page/{path}` | 删除页面 |
| `POST /api/wiki/rollback/{path}` | Git 回滚 |
| `GET /api/wiki/history` | 版本历史 |
| `GET /api/wiki/search?q=` | 搜索知识库 |
| `POST /api/wiki/import` | 导入 Markdown |
| `POST /api/wiki/auto-tag` | LLM 自动生成标签 |
| `GET /api/wiki/export` | 知识库 ZIP 导出 |
| `POST /api/chat/stream` | **SSE 流式对话** |
| `POST /api/chat/message` | 同步对话（返回 evaluation_link） |
| `POST /api/chat/confirm` | Human-in-the-Loop CRUD 确认 |

---

## 评估响应示例

```json
{
  "id": "eval-uuid",
  "task_id": "task-uuid",
  "status": "completed",
  "stream_mode": false,
  "evaluation": {
    "planning": { "coverage": 85, "ordering": 90, "granularity": 80, "completeness": 85, "overall": 85, "feedback": "..." },
    "tactical": { "relevance": 90, "efficiency": 85, "correctness": 88, "overall": 88, "feedback": "..." },
    "tool_use": { "selection_quality": 92, "parameter_accuracy": 88, "result_utilization": 85, "overall": 89, "feedback": "..." },
    "memory": { "retention": 85, "relevance": 90, "consistency": 88, "overall": 87, "feedback": "..." },
    "replan": { "trigger_appropriateness": 100, "adaptation_quality": 100, "learning_from_failure": 100, "overall": 100, "feedback": "..." },
    "retrieval": { "relevance": 80, "evidence_accuracy": 85, "coverage": 75, "overall": 80, "feedback": "...", "hallucination_detected": false, "missing_info": [] },
    "overall_score": 88.0,
    "summary": "...",
    "recommendations": ["..."]
  }
}
```

## SSE 流式事件

`POST /evaluations/stream` 返回的事件类型：

| 事件 | 数据 | 说明 |
|------|------|------|
| `progress` | `{"dimension":"planning","score":85,"progress":1,"total":6}` | 某一维度评估完成 |
| `result` | `{"scores":{...},"overall":88}` | 全部完成，含总分 |
| `error` | `{"dimension":"...","message":"..."}` | 某维度评估失败 |
| `done` | `{}` | 流结束 |
