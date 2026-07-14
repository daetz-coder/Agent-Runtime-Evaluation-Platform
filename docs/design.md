# Agent Runtime Evaluation — 设计说明

> **入口**: [README.md](../README.md) · **架构**: [architecture.md](architecture.md) · **开发者指南**: [developer_guide.md](developer_guide.md)

## 1. 为什么做 Runtime Evaluation

传统 Prompt Evaluation 只评最终输出，无法发现 Agent 在运行过程中的决策问题。本平台评估 **每一步行为质量**：

- 计划是否合理（Planning）
- 下一步动作是否恰当（Tactical）
- 工具是否选对、参数是否正确（Tool Use）
- 上下文是否保持（Memory）
- 失败后是否有效重规划（Replan）
- RAG 检索是否可靠、有无幻觉（Retrieval）

## 2. 六维评估体系

| 维度 | 权重 | 方法 |
|------|------|------|
| Planning | 20% | LLM-as-Judge |
| Tactical | 20% | LLM-as-Judge |
| Tool Use | 15% | LLM-as-Judge |
| Memory | 15% | LLM-as-Judge |
| Replan | 15% | LLM-as-Judge |
| Retrieval | 15% | LLM-as-Judge + 幻觉检测 |

默认通过 `evaluate_parallel()` 六路并发，耗时约 15–30 秒。

## 3. 架构

```
Trajectory (SDK/Wiki Agent) → EvaluationService → 6 Evaluators (并行)
                                         ↓
                                   Redis Cache (可选)
                                   • LLM 结果缓存 24h
                                   • 报表聚合 5min
                                   • Task 查询 60s
                                   • Dashboard 30s
                                   • 接口限流 Sorted Set
                                         ↓
                                    DB → Reports API → Vue Dashboard
```

## 4. Redis 缓存策略

**设计原则**: Redis 为可选依赖，不可用时应用正常运行（所有 cache 操作 try/except 后静默返回 None/False）。

| 场景 | 策略 | 理由 |
|------|------|------|
| 报表聚合 | 全量查询结果缓存，写入时 pattern DEL | 聚合查询 O(N)，Dashboard 高频刷新 |
| LLM 评估结果 | prompt SHA-256 哈希做 key，24h TTL | 相同轨迹+目标 = 相同评估结果，节省 API 费用 |
| 接口限流 | Sorted Set 滑动窗口 | 防止 LLM API 费用失控，Redis 不可用时放行 |
| Task/Trajectory | 短 TTL + 写入时失效 | 减少评估流程内重复查询（get_task 单次流程调用 2-4 次） |
| Wiki 会话 | Write-through，SQLite 为 source of truth | 每条消息都查 SQLite，加缓存后读延迟 <1ms |

## 5. 与 RAGAS / LangSmith 的差异

- **RAGAS**：专注 RAG 检索与生成质量
- **LangSmith**：通用 tracing + 实验平台
- **本平台**：Agent **运行时** 全链路六维（Planning / Tactical / Tool Use / Memory / Replan / Retrieval），含轨迹动作级分析、迭代对比、多模型共识

## 6. Wiki Agent 闭环

Wiki Agent 聊天时通过 `EvaluationTrace` 采集 trajectory（含 retrieval 步骤），可选自动触发评估，形成「Agent 运行 → 评估 → 改进」演示闭环。

## 7. 效果展示

### 前端可视化体系

| 页面 | 图表类型 | 数据来源 | 刷新时机 |
|------|----------|----------|----------|
| 仪表板 | 雷达图 + 趋势折线 + 柱状图 + 统计卡片 | `GET /reports/summary` + `GET /reports/trends` | 页面加载，缓存 30s |
| 评估详情 | 6 维评分卡 + 雷达图 + 时间线 | `GET /evaluations/{id}` | 评估完成时自动刷新 |
| 数据分析 | 分布直方图 + 热力图 + 多折线叠加 | `GET /reports/dimensions/{dim}` + `GET /reports/trends` | 页面加载 |
| Replay 调试 | 步骤展开列表，LLM 原始 Prompt/Response | `GET /evaluations/{id}/replay` | 手动点击 |
| Judge 透明面板 | 原始 Judge Prompt + Response + 解析后分数 | `GET /evaluations/{id}/judge-raw/{dim}` | 手动点击 |
| 系统设置 | 状态标签 + 配置表单 | `GET /system/health` | 页面加载 + 手动刷新 |

### 评分展示规范

| 等级 | 范围 | 颜色 | UI 展示 |
|------|------|------|---------|
| 优秀 | ≥ 80 | `success` (绿色) | 标签 + 绿色进度条 |
| 良好 | ≥ 60 | `warning` (黄色) | 标签 + 黄色进度条 |
| 一般 | ≥ 40 | `orange` (橙色) | 标签 + 橙色进度条 |
| 较差 | < 40 | `danger` (红色) | 标签 + 红色进度条 |

### Consensus 多模型对比

多模型共识评估的输出在 Dashboard 上以横向表格 + 柱状图展示：

```
═══ 规划维度 Consensus ═══
deepseek-chat:     72%  ████████████████████████████░░  72
glm-4:             75%  ██████████████████████████████  75
qwen-plus:         70%  ██████████████████████████░░░░  70
────────────────────────────────────────────────────
综合均分: 72.3  |  分歧度 (std): 2.1  |  一致性: 高 ✅
```

## 8. 关键设计要点

| 要点 | 方案 | 理由 |
|------|------|------|
| **缓存隔离** | Cache key 包含模型名 | 避免多模型共识时缓存串用导致 std=0 |
| **优雅降级** | 所有外部依赖 try/except 兜底 | Redis 等不可用时核心功能不掉 |
| **并行评估** | `asyncio.gather` 并发 6 评估器 | 单次评估 15-30s，串行需 90-180s |
| **Ghost Plan 过滤** | 跳过只有 {goal,context} 的 plan 步骤 | 避免任务创建时的空 plan 被误判为真实规划 |
| **增量重算** | Trajectory Diff → 只重算变化维度 | 修改 prompt 后节省 2/3 评估时间 |
| **版本追踪** | evaluation 记录 prompt_version / model_name | 每次评估可追溯使用的配置版本 |
