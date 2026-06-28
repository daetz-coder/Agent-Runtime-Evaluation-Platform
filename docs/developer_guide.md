# Developer Quick Start Guide

Agent 工程师快速上手指南 — 聚焦本地开发、调试和迭代。

---

## 1. 最小启动（无需 Docker）

```bash
# 安装依赖
pip install -e ".[dev]"

# Mock 模式启动后端（无需 Docker）
SANDBOX_MOCK_MODE=true python -m app.main

# 另一个终端：启动前端
cd frontend && npm install && npm run dev
```

Mock 模式下：
- Agent Runtime 返回**固定 5 步轨迹**，含 `_llm_trace`（模拟 LLM prompt/response）
- Replay Debugger 和 Judge 透明面板**有数据可显示**
- 无需启动 Docker、无需 LLM API Key

---

## 2. 快速提交一个评估

```bash
# 1. 创建任务
curl -X POST http://localhost:8000/api/v1/tasks/ \
  -H "Content-Type: application/json" \
  -d '{"goal": "分析 2024 年销售数据"}'

# 返回: {"id": "task-uuid", ...}

# 2. 提交轨迹（复制 task-uuid）
curl -X POST http://localhost:8000/api/v1/tasks/{task-uuid}/trajectory \
  -H "Content-Type: application/json" \
  -d '{
    "steps": [
      {"step_number": 1, "action_type": "plan", "action_detail": {"plan": "1) 读取数据 2) 分析 3) 出报告"}},
      {"step_number": 2, "action_type": "tool_call", "action_detail": {"tool_name": "python", "input": {"code": "print(1)"}}, "observation": "1"},
      {"step_number": 3, "action_type": "think", "action_detail": {"thought": "分析完成"}}
    ]
  }'

# 3. 运行评估
curl -X POST http://localhost:8000/api/v1/evaluations/quick \
  -H "Content-Type: application/json" \
  -d '{"task_id": "{task-uuid}"}'

# 返回: {"id": "eval-uuid", "evaluation": {"planning": {...}, "tactical": {...}, ...}}
```

---

## 3. 使用 Replay 调试器

评估完成后：

```bash
# 获取 Replay 数据（查看每步 LLM 看到了什么）
curl http://localhost:8000/api/v1/evaluations/{eval-uuid}/replay

# 返回示例:
{
  "steps": [
    {
      "step_number": 1,
      "action_type": "think",
      "llm_prompt": "[system] You are an agent...\n[human] 分析数据...",
      "llm_response": "我计划先读取 CSV 文件...",
      "llm_model": "deepseek-chat",
      "latency_ms": 1200
    }
  ]
}
```

**前端操作**：在 EvaluationDetail 页面点击 **"Replay 调试器"** 按钮 → 展开每步查看 LLM 原始输入/输出。

---

## 4. 使用 Judge 透明面板

```bash
# 获取某个维度的 judge 原始数据
curl http://localhost:8000/api/v1/evaluations/{eval-uuid}/judge-raw/planning

# 返回:
{
  "planning": {
    "dimension": "planning",
    "judge_prompt": "Evaluate this agent's planning...",
    "judge_response": "{\"coverage\": 85, \"ordering\": 90, ...}",
    "judge_model": "deepseek-chat",
    "score": 85.0,
    "score_breakdown": {"coverage": 85, "ordering": 90, ...}
  }
}
```

**前端操作**：在 EvaluationDetail 页面找到 **"Judge 透明度面板"** → 选择维度 → 点击"查看原始 Judge 输出"。

---

## 5. 对比两个轨迹 Diff

```bash
# 对比两次 evaluation 的轨迹差异
curl "http://localhost:8000/api/v1/evaluations/diff?base_evaluation_id={base-id}&head_evaluation_id={head-id}"

# 返回:
{
  "total_changes": 2,
  "steps_added": 1,
  "steps_removed": 0,
  "steps_modified": 1,
  "steps": [
    {"step_number": 3, "change_type": "added", ...},
    {"step_number": 5, "change_type": "changed", "field_changes": ["action_detail.tool"]}
  ]
}
```

---

## 6. 增量评估（只重算变化维度）

修改 agent prompt 后，不需要重跑全部 6 个评估器：

```bash
curl -X POST http://localhost:8000/api/v1/evaluations/incremental \
  -H "Content-Type: application/json" \
  -d '{
    "base_evaluation_id": "{上一次 evaluation 的 id}",
    "head_task_id": "{新任务的 id}"
  }'

# 返回:
{
  "evaluation_id": "new-eval-id",
  "reused_dimensions": ["memory", "replan", "retrieval", "tool_use"],
  "re_evaluated_dimensions": ["planning", "tactical"],
  "overall_score": 82.5
}
```

---

## 7. Golden Test Suite — 验证评估器回归

修改 evaluator 的 judge prompt 后，运行 golden suite 验证：

```bash
# 运行全部黄金案例
make golden

# 输出示例:
# ✅ PASS | golden-excellent: 优秀 Agent — all 7 dimensions passed
# ✅ PASS | golden-replan: 优秀重规划 Agent — all 7 dimensions passed
# ✅ PASS | golden-retrieval: 检索密集型 Agent — all 7 dimensions passed
# ✅ PASS | golden-tool-misuse: 工具滥用 Agent — all 7 dimensions passed
# ============================================================
#   ALL PASSED
# ============================================================

# 只运行指定案例
python -m app.benchmarks.golden.runner --case golden-excellent golden-replan

# 完整 CI 门禁（含回归检测）
make check-ci
```

---

## 8. 回归检测

```bash
# 对比两次 evaluation 的分数
curl "http://localhost:8000/api/v1/evaluations/regression/check?base_evaluation_id={基线 id}&head_evaluation_id={新 id}"

# 返回（无回归）:
{
  "has_regression": false,
  "overall_change": 3.5,
  "summary": "No regression. Overall: 78.0 → 81.5 (+3.5)."
}

# 返回（有回归）:
{
  "has_regression": true,
  "overall_change": -8.0,
  "dimensions": {
    "planning": {"base_score": 85, "head_score": 72, "delta": -13, "is_regression": true}
  },
  "summary": "Regression detected! Overall: 80.0 → 72.0 (-8.0). Regressed dimensions: planning: 85→72 (-13)"
}
```

---

## 9. 使用 Makefile 加速开发

```bash
make help          # 查看所有可用命令
make lint          # ruff 自动修复
make typecheck     # mypy 类型检查
make test          # 全部测试
make test-fast     # 快速测试（跳过 Milvus 相关测试）
make test-cov      # 测试 + 覆盖率报告
make run           # 启动后端
make run-dev       # 热重载启动
make golden        # Golden Test Suite
make check-ci      # CI 门禁
```

---

## 10. 版本追踪

每个 Evaluation 记录会自动包含版本信息：

```json
{
  "id": "eval-uuid",
  "prompt_version": "v1.1",
  "model_name": "deepseek-chat",
  "model_provider": "deepseek",
  ...
}
```

修改 `app/agent_runtime/prompts/` 目录下的 YAML 模板来创建新版本。
修改 evaluator judge prompt 后，建议运行 `make golden` 确认评分范围没有被破坏。

---

## 11. Agent in Sandbox（沙箱评估）

Agent 在 Docker 容器内运行，平台完全控制执行环境：

```bash
# 沙箱评估 — Agent 在容器内运行 python/bash/file 工具
curl -X POST http://localhost:8000/api/v1/evaluations/run \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "读取 data.csv 计算平均销售额并保存到 result.txt",
    "workspace_files": {
      "data.csv": "month,sales\nJan,100\nFeb,200\nMar,150"
    },
    "tools": ["python_execute", "file_read", "file_write"]
  }'

# 返回完整评估结果（6 维分数 + Agent 运行元数据）
```

**SSE 流式模式**（实时查看 Agent 每步操作）：

```bash
curl -N -X POST http://localhost:8000/api/v1/evaluations/run/stream \
  -H "Content-Type: application/json" \
  -d '{"goal": "计算 Fibonacci 前 10 项"}'

# 事件流:
# event: agent_step    {"step_number":1,"action_type":"think",...}
# event: agent_done    {"success":true,"steps_taken":5}
# event: eval_progress {"dimension":"planning","score":85}
# event: result        {"evaluation":{...}}
# event: done
```

**Mock 模式**（无需 Docker 开发）：

```bash
SANDBOX_MOCK_MODE=true python -m app.main
# Agent Runtime 返回固定 5 步轨迹，含 _llm_trace
```

---

## 12. 可观测性

### 结构化日志

所有日志自动包含 `request_id`（Correlation ID）：

```
2024-01-15T10:30:00Z [info] Evaluation completed [eval_service] task_id=abc request_id=f3a2c1
```

通过 `X-Request-ID` 请求头传递或自动生成。

### OpenTelemetry 链路追踪

```bash
# 启动 Jaeger（可选）
docker run -d --name jaeger -p 16686:16686 -p 4317:4317 jaegertracing/all-in-one

# 启动应用（ENABLE_TRACING=true，默认开启）
python -m app.main

# 访问 Jaeger UI
open http://localhost:16686
```

Trace 结构：
```
sandbox_evaluation (5min)
├── session_acquire (10ms)
├── workspace_setup (200ms)
├── agent_loop (4min)
│   ├── step_0_think_and_act
│   │   ├── llm_call (3s, provider=deepseek)
│   │   └── tool_execute: python_execute (2s)
│   ├── step_1_think_and_act
│   │   ├── llm_call (3s)
│   │   └── tool_execute: file_read (50ms)
│   └── ...
├── trajectory_persist (20ms)
└── evaluation (15s, 6 evaluators parallel)
```

### Prometheus 指标

```bash
# 查看指标
curl http://localhost:8000/api/v1/system/metrics

# 关键指标:
# agent_eval_evaluation_total{status,mode}        — 评估总数
# agent_eval_evaluation_duration_seconds{mode}    — 评估耗时分布
# agent_eval_llm_calls_total{provider,model}      — LLM 调用次数
# agent_eval_tool_calls_total{tool,status}        — 工具调用次数
# agent_eval_sandbox_active_sessions              — 活跃沙箱数
# agent_eval_http_requests_total{method,endpoint} — HTTP 请求数
```

---

## 13. Celery 任务队列

评估任务通过 Celery 异步执行（自动重试、并发控制）：

```bash
# 启动 Celery worker（另一个终端）
celery -A app.celery_app worker -l info -c 4 -Q evaluation,sandbox

# 评估请求自动路由到 Celery（如果可用）
# 不可用时 fallback 到 FastAPI BackgroundTasks
```

---

## 14. 多租户资源配额

Workspace 级别的资源限制：

| 配额 | 默认值 | 说明 |
|------|--------|------|
| `sandbox_quota` | 3 | 同时运行的沙箱数 |
| `max_steps_per_eval` | 50 | 单次评估最大 Agent 步数 |
| `eval_count_limit_monthly` | 1000 | 月评估次数上限 |
| `storage_limit_mb` | 1024 | workspace 存储上限 |

超限时 API 返回 HTTP 429 + 详细错误信息。
