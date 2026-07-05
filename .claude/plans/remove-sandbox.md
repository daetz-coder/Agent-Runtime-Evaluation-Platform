# 移除 Sandbox，统一为 SDK 单路径

## 目标
移除所有 Sandbox 相关代码，只保留 SDK 采集路径。

## 移除范围

### 1. 整个 `app/agent_runtime/` 目录（20+ 文件）
全部是 Sandbox 专用，无共享依赖。

### 2. Sandbox API 端点
- `app/api/v1/endpoints/evaluation.py` — 删除 `/run` 和 `/run/stream` 端点、`_is_sandbox_ready()`
- `app/models/schemas.py` — 删除 `SandboxEvalRequest`、`AgentRunInfo`、`SandboxEvalResponse`

### 3. Sandbox 服务层
- `app/services/evaluation_service.py` — 删除 `run_sandbox_evaluation()` 方法
- `app/services/system_health.py` — 删除 `sandbox_health` 部分
- `app/services/quota.py` — 删除 `check_sandbox_quota()`、`SANDBOX_EVAL_MODE`

### 4. Sandbox 基础设施
- `app/main.py` — 删除 sandbox 初始化/关闭代码
- `app/celery_app.py` — 删除 sandbox Celery 任务
- `app/core/config.py` — 删除 `SANDBOX_*` 和 `AGENT_*` 配置
- `app/core/metrics.py` — 删除 sandbox 专用指标

### 5. Sandbox 测试
- `tests/test_sandbox.py`
- `tests/test_mock_and_versioning.py`
- `tests/test_agent_runtime.py`
- `tests/test_llm_trace.py`

### 6. Sandbox 文档
- `docs/1-sandbox.md`
- 其他文档中的 sandbox 引用

## 保留项
- `app/agent_runtime/prompts/` — PROMPT_VERSION 被 evaluation_service 和 settings 使用
- SDK 全部代码不变
- Wiki Agent 全部代码不变
- 评估器全部代码不变

## 执行顺序
1. 删除 `app/agent_runtime/` 目录（保留 prompts/）
2. 清理 evaluation_service.py
3. 清理 evaluation.py API 端点
4. 清理 schemas.py
5. 清理 main.py、celery_app.py、config.py、metrics.py
6. 清理 system_health.py、quota.py
7. 删除 sandbox 测试文件
8. 更新文档
