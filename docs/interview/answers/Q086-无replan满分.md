# Q086: 没有 replan 事件时默认满分 100——请解释这个设计逻辑，是否合理？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q086 |
| 分类 | 六维评估器深入 |
| 难度 | ★★★ |

## 问题

没有 replan 事件时默认满分 100——请解释这个设计逻辑，是否合理？

## 参考答案

**首先需要纠正一个常见误解：代码并没有在无 replan 时给满分 100。** 实际行为是将该维度标记为"不适用"并从综合评分中完全剔除，这与满分 100 有本质区别。

**实际行为分析。** `replan_evaluator.py:111-121` 中，当 `replan_events` 为空且 `missed_opportunities` 为空时，返回的 `ReplanScore` 设置 `applicable=False`，所有子维度分数为 0，overall 为 0，并附带原因说明"Agent 顺利完成未触发重规划，该维度已从综合评分中剔除"。关键字段是 `applicable=False`。

**`applicable=False` 的下游影响。** 在 `scoring.py:8-12` 中，`is_applicable` 函数检查 `applicable` 字段，当其为 `False` 时返回 `False`。`weighted_overall` 函数（`scoring.py:25-44`）在计算加权总分时会跳过不适用的维度——既不加入分子，也不加入分母。这意味着 replan 维度的 0.15 权重会被完全移除，其余五个维度的权重自动归一化。例如，原本 planning(0.20) 的贡献是 `0.20 x score / 1.0`，replan 剔除后变为 `0.20 x score / 0.85`，相当于权重被放大了约 17.6%。

**设计逻辑的核心是"不适用"不等于"满分"。** 如果 Agent 顺利完成任务，没有触发任何重规划，这说明它的首次执行策略是成功的。在这种情况下，给 replan 维度打 100 分（暗示重规划能力优秀）是不合理的——我们根本没有观察到任何重规划行为，无法评价其质量。同样，打 0 分也是不公平的——Agent 没有犯错，不应该因为"没有展示重规划能力"而被扣分。最合理的做法正是当前的设计：标记为不适用，从评分中剔除。

**但存在一个检测机制防止遗漏。** `_detect_missed_replans` 方法（`replan_evaluator.py:162-195`）会扫描整个 trajectory，检测是否有连续 5 次失败（通过 `tool_call` 的 observation 中包含 "error"、"failed"、"not found"、"exception" 等关键词判断）但没有触发 replan 的情况。如果检测到 `missed_opportunities`，即使没有实际的 replan 事件，也会进入 LLM Judge 评估流程，给 Agent 一个反映"应该重规划但没有"的低分。这就区分了两种情况：

- **无 replan 且无遗漏**（`applicable=False`）：Agent 顺利完成，维度剔除
- **无 replan但有遗漏**（进入 LLM 评估）：Agent 应该重规划但没有，会被扣分

**设计的合理性讨论。** 这个设计总体是合理的，但存在一个潜在盲区：如果 Agent 虽然最终完成了任务，但经历了大量不必要的迂回（多次无效尝试后碰巧成功），它既没有触发 replan（因为没有连续 5 次失败），也没有 missed_opportunities（因为失败不连续）。这种情况下，replan 维度被剔除，Agent 不会因为缺乏规划调整能力而受到任何惩罚。要覆盖这种情况，可以考虑增加"总失败次数"或"执行效率"的检测阈值，而不仅仅依赖连续失败。

**权重重新分配的实际影响。** 以一个具体例子说明：假设某 Agent 在 planning(80)、tactical(70)、tool_use(75)、memory(65)、retrieval(70) 上得分，replan 不适用。原始加权总分 = `80x0.20 + 70x0.20 + 75x0.15 + 65x0.15 + 70x0.15 + replan_x0.15`。replan 剔除后，总分 = `(80x0.20 + 70x0.20 + 75x0.15 + 65x0.15 + 70x0.15) / 0.85 = 58.25 / 0.85 = 68.5`。如果没有剔除机制且 replan=50，总分 = `58.25 + 50x0.15 = 65.75`。差异约 2.8 分，replan 权重越高差异越大。

## 代码依据

- `app/evaluators/replan_evaluator.py:111-121` — 无 replan 且无 missed_opportunities 时返回 applicable=False
- `app/evaluators/replan_evaluator.py:162-195` — _detect_missed_replans 检测连续 5 次失败未 replan
- `app/evaluators/replan_evaluator.py:74-78` — WEIGHTS: trigger_appropriateness=0.35, adaptation_quality=0.35, learning_from_failure=0.30
- `app/evaluators/scoring.py:8-12` — is_applicable 检查 applicable 字段
- `app/evaluators/scoring.py:25-44` — weighted_overall 跳过不适用维度并归一化权重
- `app/core/config.py:136-143` — EVAL_DIMENSION_WEIGHTS 中 replan=0.15
- `app/models/schemas.py:205-212` — ReplanScore 模型定义，applicable 字段默认 True

## 回答要点

- 代码并非给满分 100，而是设置 applicable=False 将维度从评分中完全剔除
- applicable=False 时 weighted_overall 跳过该维度，权重自动归一化
- "不适用"不等于"满分"——没有观察到重规划行为就无法评价其质量
- _detect_missed_replans 检测连续 5 次失败未 replan 的情况，此时仍会进入 LLM 评估
- 设计盲区：非连续失败的迂回执行不会被检测到
- 权重重新分配使剩余五维权重放大，replan=0.15 剔除后其余维度权重约放大 17.6%

## 常见追问

**Q: applicable=False 和 overall=0 有什么区别？下游如何处理？**

A: `overall=0` 但 `applicable=True` 时，该维度会以 0 分参与加权计算，拉低总分。`applicable=False` 时，`is_applicable` 返回 False，`weighted_overall` 完全跳过该维度。这是两个完全不同的语义。当前 replan 的"不适用"返回两者都是（overall=0 且 applicable=False），但真正起剔除作用的是 applicable 字段。

**Q: 如果所有维度都不适用怎么办？**

A: `scoring.py:42-43` 中，如果 `denominator <= 0`（所有维度都被剔除），`weighted_overall` 返回 0.0。这是一种极端情况，实际中不太可能出现——至少 planning 和 tactical 维度几乎总是适用的。

**Q: missed_opportunities 的阈值 5 次连续失败是否合理？**

A: 5 次是一个经验值。太低（如 2-3 次）会导致误判——偶发的工具错误不意味着需要重规划。太高（如 10 次）则会放过真正需要重规划的情况。5 次给了 Agent 一定的容错空间，同时在明显陷入循环时触发评估。可以考虑将阈值做成可配置项。

**Q: 能否给"无 replan 且成功"的 Agent 一个明确的高分而非剔除？**

A: 技术上可以，但逻辑上不自洽。Replan 维度的三个子维度（trigger_appropriateness、adaptation_quality、learning_from_failure）都需要观察到重规划行为才能评价。给一个没有重规划的 Agent 打高分，等于在没有证据的情况下假设它"如果需要重规划一定能做好"，这是一种不合理的推断。

## 相关题目

- [Q087](../answers/Q087-trigger-appropriateness.md)
- [Q088](../answers/Q088-failure与replan.md)
- [Q089](../answers/Q089-Replan评估缺口.md)
