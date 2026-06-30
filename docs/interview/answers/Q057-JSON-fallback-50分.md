# Q057: JSON 解析失败时 fallback 到 50 分，这个策略合理吗？有没有更好的降级方案？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q057 |
| 分类 | LLM-as-Judge 评估体系 |
| 难度 | ★★★ |

## 问题

JSON 解析失败时 fallback 到 50 分，这个策略合理吗？有没有更好的降级方案？

## 参考答案

所有六维 Evaluator 在解析 Judge LLM 返回的 JSON 失败时，统一将各子维度 fallback 到 50 分。这个策略有其合理性，但也存在明显缺陷。

**为什么选择 50 分？** 50 是 0-100 量表的中位数，代表"最大不确定性"。当 Judge LLM 无法输出有效 JSON 时，我们既不知道它想给高分还是低分，选择中位数避免了两个极端错误：给 0 分会不公平地惩罚被评估 Agent，给 100 分则会虚高。这是一种保守的中性策略。

**具体实现因 Evaluator 而异。** Planning、ToolUse、Replan 三个 Evaluator 使用相同的 bracket-find 策略（`content.find("{")` + `content.rfind("}")`），在 `json.loads` 抛出 `JSONDecodeError` 时 fallback。例如 `planning_evaluator.py:204-225` 中，解析失败返回 `{"coverage": 50, "ordering": 50, "granularity": 50, "completeness": 50, "feedback": content}`，保留原始响应内容供调试。Retrieval Evaluator 则使用正则 `re.search(r"\{.*\}", content, re.DOTALL)` 提取 JSON（`retrieval_evaluator.py:171`），这是一种更健壮的方式——即使 LLM 在 JSON 前后输出了额外文本也能正确提取。但正则方式也有边界情况：如果 LLM 响应中包含代码块里的 JSON 片段，可能会匹配到错误的 JSON。

**50 分的真实问题在于它仍然是一个有效信号。** 假设 6 个维度中有 1 个 fallback 到 50，其余 5 个维度的加权总分是 80。那么最终 overall = 80 x 0.85 + 50 x 0.15 = 75.5，比真实水平低了约 4.5 分。如果 fallback 的维度权重更高（如 planning=0.20），偏差可达 6 分。更关键的是，50 分会被计入加权平均的分母，拉低整体得分，而这个 50 分完全是噪声。

**当前系统的透明性机制。** `_invoke_llm_cached` 方法（`base.py:294-372`）会将 Judge LLM 的原始 prompt、response、model、latency 等存入 `_last_judge_raw` 和 `_judge_raw_history`，前端的 Judge 透明度面板可以展示这些数据，让用户看到 JSON 解析失败的事实。这是一种"事后可审计"的兜底，但不能从根本上解决分数失真问题。

**更好的降级方案有四种：**

1. **标记 N/A 并从 overall 中剔除。** 参照 Replan 维度的 `applicable=False` 机制（`scoring.py:8-12`），当 `is_applicable` 返回 False 时，该维度不参与加权计算，权重被重新归一化。JSON 解析失败时也可以设置 `applicable=False`，让该维度完全不影响总分。

2. **置信度加权。** 将 50 分的权重设为 0，只在有明确信号时才计入。这与方案 1 类似，但更细粒度——可以在子维度级别操作。

3. **重试 + 简化 prompt。** JSON 解析失败后，用更简单的 prompt（只要求返回一个数字而非完整 JSON）重试一次。这增加了 API 调用成本，但比直接 fallback 50 更准确。

4. **使用 Structured Output / Function Calling。** 从根源上解决 JSON 格式问题。OpenAI、Anthropic 等厂商都支持强制 JSON 输出模式，可以保证返回合法 JSON，彻底消除解析失败。

**temperature=0 的作用与局限。** 所有 Evaluator 使用 `temperature=0`（`base.py:50-88`），这最大程度减少了 LLM 输出的随机性，从而降低了 JSON 格式错误的概率。但 temperature=0 不能完全消除问题——某些 LLM（尤其是非 OpenAI 的模型）仍然可能返回 markdown 包裹的 JSON（如 `` ```json ... ``` ``）或截断的响应。

## 代码依据

- `app/evaluators/planning_evaluator.py:204-225` — bracket-find + json.loads，失败时 4 个子维度 fallback 50
- `app/evaluators/replan_evaluator.py:289-307` — 相同模式，3 个子维度 fallback 50
- `app/evaluators/tool_use_evaluator.py:193-211` — 相同模式，3 个子维度 fallback 50
- `app/evaluators/retrieval_evaluator.py:166-199` — 使用 re.search 正则提取，失败时 3 个子维度 + overall 均 fallback 50
- `app/evaluators/base.py:294-372` — _invoke_llm_cached 存储原始 Judge 数据供透明度展示
- `app/evaluators/base.py:50-88` — _get_default_llm 所有 provider 均设 temperature=0
- `app/evaluators/scoring.py:8-12` — is_applicable 检查 applicable 字段，False 时剔除维度
- `app/graphs/evaluation_graph.py:113-128` — evaluate_planning 捕获异常返回 overall=0

## 回答要点

- 50 是 0-100 中位数，代表最大不确定性，避免极端惩罚或奖励
- Planning/ToolUse/Replan 用 bracket-find 提取 JSON，Retrieval 用正则提取，策略不统一
- 50 分仍是有效信号，会拉低加权平均，1 个维度 fallback 可偏差 4-8 分
- _invoke_llm_cached 保留原始响应，前端透明度面板可展示失败原因
- 更好的方案：N/A 剔除（参照 applicable=False）、置信度加权、重试简化 prompt、Structured Output
- temperature=0 降低但不消除 JSON 失败概率，某些 LLM 仍返回 markdown 包裹的 JSON

## 常见追问

**Q: 为什么不同 Evaluator 的 JSON 提取方式不统一？**

A: Planning、ToolUse、Replan 使用简单的 bracket-find（`find("{")` + `rfind("}")`），实现简单但容易受 LLM 输出中多余花括号干扰。Retrieval Evaluator 使用 `re.search(r"\{.*\}", content, re.DOTALL)` 正则，能跳过前导文本，但如果响应中有多个 JSON 对象可能匹配到错误的。理想情况应该统一为正则或 Structured Output。

**Q: 如果 Judge LLM 总是返回 markdown 包裹的 JSON 怎么办？**

A: 可以在 `_parse_scores` 中增加 strip markdown fence 的逻辑（去掉 `` ```json `` 和 `` ``` ``），或者在 prompt 中明确要求"只返回 JSON，不要 markdown 代码块"。更好的方案是使用 OpenAI 的 `response_format={"type": "json_object"}` 或 Anthropic 的 tool_use 来强制结构化输出。

**Q: applicable=False 剔除维度后，权重如何重新分配？**

A: `scoring.py:25-44` 中 `weighted_overall` 函数遍历所有维度，跳过 `is_applicable` 返回 False 的维度，只对剩余维度的权重求和作为分母。这相当于自动归一化——如果 replan(0.15) 被剔除，其余五维的权重会按比例放大，总分仍保持 0-100 量表。

**Q: 重试方案的成本如何控制？**

A: 可以限制最多重试 1 次，且重试时使用更短的 prompt（只要求返回 JSON 对象，不需要 feedback 字段）。加上 `_invoke_llm_cached` 的 Redis 缓存机制，同一评估的重试结果会被缓存，不会重复调用。

## 相关题目

- [Q054](../answers/Q054-LLM-as-Judge.md)
- [Q055](../answers/Q055-temperature为零.md)
- [Q058](../answers/Q058-JSON抽取漏洞.md)
- [Q059](../answers/Q059-Structured-Output.md)
