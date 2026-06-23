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
```

## 4. 与 RAGAS / LangSmith 的差异

- **RAGAS**：专注 RAG 检索与生成质量
- **LangSmith**：通用 tracing + 实验平台
- **本平台**：Agent **运行时** 全链路五维 + RAG 六维，含轨迹动作级分析、迭代对比、多模型共识

## 5. Wiki Agent 闭环

Wiki Agent 聊天时通过 `EvaluationTrace` 采集 trajectory（含 retrieval 步骤），可选自动触发评估，形成「Agent 运行 → 评估 → 改进」演示闭环。
