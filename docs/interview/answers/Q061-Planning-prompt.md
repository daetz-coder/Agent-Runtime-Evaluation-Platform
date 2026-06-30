# Q061: 请描述 Planning Evaluator 的 prompt 结构：输入是什么？要求 Judge 输出哪些字段？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q061 |
| 分类 | LLM-as-Judge 评估体系 |
| 难度 | ★★ |

## 问题

请描述 Planning Evaluator 的 prompt 结构：输入是什么？要求 Judge 输出哪些字段？

## 参考答案

Planning Evaluator 的 prompt 模板定义在 `app/evaluators/planning_evaluator.py:18-66` 的 `PLANNING_EVALUATION_PROMPT` 常量中，整体结构分为输入、评分标准和输出格式三个部分。

**输入部分**：prompt 接收三个变量——`{goal}`（用户目标任务描述）、`{plan}`（Agent 的计划文本）、`{context}`（额外上下文信息）。其中 plan 文本由 `_format_plan()`（第 149-179 行）和 `_format_plan_updates()`（第 181-202 行）生成。`_format_plan()` 会先尝试提取结构化的 steps/milestones 列表，逐条格式化为编号文本；如果没有结构化步骤，则退而取 goal/plan/content 字段直接展示。`_format_plan_updates()` 处理动态计划更新事件，输出每步的 next_action、reason、milestone_status 和 remaining_steps。

**评分标准部分**：prompt 要求 Judge 从 4 个子维度打分（每项 0-100 分）：

1. **覆盖率（Coverage）**（第 33-37 行）：计划是否覆盖所有必要里程碑，是否遗漏分析、实现、测试、文档等关键阶段。
2. **顺序性（Ordering）**（第 39-42 行）：步骤顺序是否合理，依赖关系是否正确。
3. **粒度（Granularity）**（第 44-48 行）：细化程度是否适当——过细（如"阅读第 20 行"）和过粗（如"实现所有功能"）都扣分，好的粒度如"实现 OAuth 流程"。
4. **完整性（Completeness）**（第 50-53 行）：是否覆盖目标所有方面，是否考虑边界情况，是否有明确完成状态。

**输出格式部分**（第 55-65 行）：要求 Judge 返回 JSON 对象，包含 8 个字段：

```json
{
    "coverage": <分数>,
    "ordering": <分数>,
    "granularity": <分数>,
    "completeness": <分数>,
    "overall": <加权平均>,
    "feedback": "<详细评估反馈（中文）>",
    "missing_milestones": ["缺失的关键步骤列表"],
    "suggestions": ["改进建议列表"]
}
```

**Prompt 语言**：整个模板以中文编写，开头明确要求"你必须用中文输出所有内容"，这是为适配中文 LLM Judge（如 DeepSeek、GLM、Qwen）设计的。在 `evaluate()` 方法（第 79-147 行）中，prompt 通过 `ChatPromptTemplate.from_template()` 构建，与 LLM 组成 chain 后调用 `_invoke_llm_cached()` 执行（第 121-128 行）。最终 4 个子维度分数按 `WEIGHTS`（第 72-77 行：coverage 0.3、ordering 0.2、granularity 0.2、completeness 0.3）计算加权总分。

**解析与容错**：Judge 返回的 JSON 通过 `_parse_scores()`（第 204-225 行）解析，先用字符串定位提取 `{...}` 子串再 `json.loads`；解析失败时回退到 4 个维度各 50 分的默认值。

## 代码依据

- `app/evaluators/planning_evaluator.py:18-66` — PLANNING_EVALUATION_PROMPT 完整模板
- `app/evaluators/planning_evaluator.py:33-37` — Coverage 评分标准
- `app/evaluators/planning_evaluator.py:39-42` — Ordering 评分标准
- `app/evaluators/planning_evaluator.py:44-48` — Granularity 评分标准
- `app/evaluators/planning_evaluator.py:50-53` — Completeness 评分标准
- `app/evaluators/planning_evaluator.py:56-65` — 输出 JSON schema（8 个字段）
- `app/evaluators/planning_evaluator.py:72-77` — WEIGHTS 权重配置
- `app/evaluators/planning_evaluator.py:79-147` — evaluate() 方法，组装 prompt 并调用 LLM
- `app/evaluators/planning_evaluator.py:149-179` — _format_plan，格式化结构化/非结构化计划
- `app/evaluators/planning_evaluator.py:181-202` — _format_plan_updates，格式化计划更新事件
- `app/evaluators/planning_evaluator.py:204-225` — _parse_scores，JSON 解析及回退策略

## 回答要点

- Prompt 输入三要素：goal（任务目标）、plan（格式化后的计划文本）、context（额外上下文）
- 4 个子维度评分标准：Coverage、Ordering、Granularity、Completeness，各 0-100 分
- 输出 JSON 含 8 个字段：4 个分数 + overall + feedback + missing_milestones + suggestions
- Prompt 全中文，适配中文 LLM Judge（DeepSeek、GLM、Qwen）
- _format_plan() 处理结构化和非结构化两种计划格式，_parse_scores() 有 JSON 解析回退策略

## 常见追问

**Q: 为什么 overall 不直接由 LLM 计算，而是在代码中用加权公式算？**

A: 让 LLM 自行计算加权平均不可靠——它可能用错权重或做错算术。代码中 `evaluate()` 第 134 行显式调用 `_calculate_weighted_score(scores, self.WEIGHTS)` 计算，权重为 coverage 0.3、ordering 0.2、granularity 0.2、completeness 0.3。虽然 prompt 中要求 LLM 输出 overall 字段，但实际使用的是代码计算值，LLM 的 overall 仅作参考。

**Q: 如果 trajectory 中没有任何 plan 类型的步骤会怎样？**

A: `evaluate()` 第 100-108 行处理这种情况：如果 `_extract_plans()` 和 `_extract_plan_updates()` 都返回空列表，直接返回 `PlanningScore(overall=0, feedback="No planning steps found...")`，不调用 LLM。

## 相关题目

- [Q054](../answers/Q054-LLM-as-Judge.md)
- [Q040](../answers/Q040-评估工作流.md)
