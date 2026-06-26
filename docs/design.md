# Agent Runtime Evaluation — 设计说明

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
Trajectory (SDK/Wiki Agent) → EvaluationService → 6 Evaluators → DB → Reports API → Vue Dashboard
                                         ↓                    ↓
                                   Redis Cache          Redis Cache
                              (LLM 结果缓存 24h)   (报表聚合 5min, Task 60s,
                                                    Dashboard 30s, 限流 Sorted Set)
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
- **本平台**：Agent **运行时** 全链路五维 + RAG 六维，含轨迹动作级分析、迭代对比、多模型共识

## 6. Wiki Agent 闭环

Wiki Agent 聊天时通过 `EvaluationTrace` 采集 trajectory（含 retrieval 步骤），可选自动触发评估，形成「Agent 运行 → 评估 → 改进」演示闭环。
