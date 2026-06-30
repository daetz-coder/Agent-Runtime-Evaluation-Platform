# Q162: 用户反馈「Planning 分数总是很低」，你的排查步骤是什么？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q162 |
| 分类 | 调试、排错与案例分析 |
| 难度 | ★★ |

## 问题

用户反馈「Planning 分数总是很低」，你的排查步骤是什么？

## 参考答案

遇到 Planning 维度持续低分的投诉，我会按以下顺序系统排查，从数据层到模型层逐层定位根因。

**第一步：确认 trajectory 是否包含规划动作。** PlanningEvaluator 的 `evaluate()` 方法在第 100 行做了一个前置检查：如果 trajectory 中既没有 `plan` 也没有 `plan_update` 类型的步骤，直接返回全零分并附带 "No planning steps found" 的 feedback。这是最常见的根因——Agent 根本没有生成结构化计划，只是直接发起工具调用。此时问题不在评估器，而在被测 Agent 的 prompt 或架构设计。

**第二步：检查是否命中了 ghost plan 过滤。** 即使 trajectory 中存在 `action_type == "plan"` 的步骤，`_extract_plans()`（base.py:139-157）会过滤掉 "ghost plans"——即 `action_detail` 只包含 `goal` 和 `context` 两个 key、缺少 `steps`/`milestones`/`plan`/`content` 的记录。这类记录通常是任务创建的副产物而非真正的规划输出。可以通过 replay 端点查看原始 action_detail 确认。

**第三步：查看 judge 原始交互。** 调用 `GET /evaluations/{id}/judge-raw` 端点（evaluation.py:1114-1142），获取 LLM judge 收到的 prompt 和返回的原始响应。重点检查：(1) 送给 judge 的 plan_text 是否完整、格式是否清晰；(2) judge 返回的是否是合法 JSON。`_parse_scores()` 在第 204-225 行做 JSON 解析，如果 judge 返回的内容被 markdown 代码块包裹（如 `` ```json ... ``` ``），`content.find("{")` 仍能正确提取，但若返回纯文本描述则会 fallback 到全部 50 分。

**第四步：检查 LLM 语言能力。** Planning 评估的 prompt 使用中文编写。如果配置的 judge 模型不擅长中文理解，评分质量会下降。可以在 judge-raw 响应中观察 judge 是否给出了合理的中文 feedback。

**第五步：检查权重配置。** Planning 的子维度权重为 coverage=0.2, ordering=0.2, granularity=0.2, completeness=0.3（planning_evaluator.py:72-77），completeness 占比最高。如果 Agent 的计划覆盖不全，即使其他维度尚可，overall 也会被拉低。

## 代码依据

- `app/evaluators/planning_evaluator.py:100-108` — 无 plan/plan_update 时直接返回全零分
- `app/evaluators/base.py:139-157` — `_extract_plans` 过滤 ghost plans（仅有 goal/context 无结构化内容）
- `app/evaluators/planning_evaluator.py:204-225` — `_parse_scores` JSON 解析失败时 fallback 到 50 分
- `app/api/v1/endpoints/evaluation.py:1114-1142` — judge-raw 端点查看 LLM 原始交互
- `app/api/v1/endpoints/evaluation.py:1056-1108` — replay 端点逐步回放 trajectory
- `app/models/action_types.py:12-13` — PLAN 和 PLAN_UPDATE 常量定义

## 回答要点

- 首先排查 trajectory 是否包含 plan 类型步骤，无规划动作则全零分是预期行为
- ghost plan 过滤机制会跳过仅有 goal/context 的伪计划，需确认 Agent 输出是否被误判
- 通过 judge-raw 端点透明查看 LLM judge 的输入输出，定位是 prompt 问题还是解析问题
- JSON 解析失败时 fallback 到 50 分，需检查 judge 是否返回了非 JSON 格式
- 中文 prompt 对英文-only 模型可能存在理解偏差

## 常见追问

**Q: 如果确认 Agent 确实不生成 plan，有什么改进建议？**

A: 两个方向：(1) 在 Agent 的 system prompt 中明确要求先输出结构化计划再执行，引导生成 `action_type=plan` 的步骤；(2) 如果业务场景确实不需要显式规划（如简单问答），可以考虑将 Planning 维度标记为 not_applicable，避免拉低综合分。

**Q: fallback 到 50 分是否合理？会不会掩盖真实问题？**

A: 50 分是一个中性默认值，避免 JSON 解析失败导致极端分数。但确实会掩盖问题——建议在 feedback 中标注 "Score fallback due to parse error"，并在监控中对 fallback 比例设置告警。长期应优化 prompt 使 judge 输出稳定的 JSON。

## 相关题目

- [Q171](../answers/Q171-extract-tool-calls.md)
- [Q175](../answers/Q175-新增Safety维.md)
