# Q22: 长对话场景下，轨迹可能非常长，评估时如何处理 token 超限？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q022 |
| 分类 | Agent 架构与设计理念 |
| 难度 | ★ |

## 问题

长对话场景下，轨迹可能非常长，评估时如何处理 token 超限？

## 参考答案

长轨迹 token 超限策略：BaseEvaluator._format_trajectory 全文拼接；各 Evaluator 可截断 action_detail（如 [:150]）。sdk _short limit 4000；collector 批量上报也截断。改进方向：按维提取相关步骤（Tool Use 只送 tool 对）、summarize 中间 think、或 sliding window + 关键 step 保留。当前实现依赖 LLM 上下文窗口（DeepSeek 等）。

## 代码依据

- `app/evaluators/base.py`
- `sdk/collector.py`
- `app/evaluators/tactical_evaluator.py`

## 回答要点

- 当前全量 format，长轨迹有风险
- _short 4000 字符截断
- 可按维过滤步骤降 token
- 评估成本与轨迹长度线性相关

## 常见追问

**Q: 128K 够吗？**

A: 六维并行 × 全轨迹仍贵，应预处理。

**Q: 如何采样？**

A: 保留 plan/failure/replan/首尾 tool 对。

## 相关题目

- [Q021](../answers/Q021-context与Memory.md)
- [Q023](../answers/Q023-多轮与子任务.md)
