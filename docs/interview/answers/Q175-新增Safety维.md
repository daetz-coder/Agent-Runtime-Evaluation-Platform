# Q175: 新增第七维 Evaluator「Safety」，评估 Agent 是否输出有害内容，需要改哪些文件？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q175 |
| 分类 | 编码与现场设计题 |
| 难度 | ★★ |

## 问题

新增第七维 Evaluator「Safety」，评估 Agent 是否输出有害内容，需要改哪些文件？

## 参考答案

新增 Safety 维度需要改动 7 个位置，涵盖后端评估器、状态模型、配置、图编排、服务层和前端展示。

**1. 新建评估器文件 `app/evaluators/safety_evaluator.py`。** 继承 `BaseEvaluator`（base.py:32-373），定义 SafetyScore pydantic 模型（含 toxicity、bias、privacy_leak、harmful_instruction 等子维度），实现 `evaluate()` 方法：从 trajectory 中提取 Agent 的文本输出（observation 和 think 步骤），构造中文 prompt 送入 LLM judge 评分，实现 `_parse_scores()` 解析 JSON 响应。子维度权重在类变量 `WEIGHTS` 中定义。

**2. 修改 `app/models/schemas.py`。** 添加 `SafetyScore` pydantic 模型，字段与评估器中的子维度对应。同时在 `OverallEvaluation` 模型中增加 `safety: SafetyScore` 字段。

**3. 修改 `app/core/config.py:136-143`。** 在 `EVAL_DIMENSION_WEIGHTS` 字典中添加 `"safety": 0.15`。原有六个维度权重总和为 1.0，需要重新归一化。例如将 planning 从 0.20 调为 0.17，tactical 从 0.20 调为 0.17，其余保持 0.15，使七维度权重总和为 1.0。

**4. 修改 `app/graphs/evaluation_graph.py`。** 三处改动：(a) `EvaluationState` TypedDict（第 50-69 行）增加 `safety_score: Optional[Dict[str, Any]]` 字段；(b) `EVALUATOR_CLASSES` 字典（第 480-487 行）增加 `"safety": SafetyEvaluator`；(c) 新增 `evaluate_safety` 异步节点函数，模式与 `evaluate_planning`（第 113 行起）一致，调用 SafetyEvaluator 并将结果写入 state 的 safety_score。同时在 `aggregate_results`（第 221-290 行）中增加 safety 的提取、`_with_defaults` 调用和 `OverallEvaluation` 构造。

**5. 修改 `app/services/evaluation_service.py`。** 在维度处理逻辑中增加 safety_score 的读取和持久化，确保评估结果写入数据库时包含 Safety 维度。

**6. 修改前端 `frontend/src/views/EvaluationDetail.vue`。** 在评估详情页的维度雷达图和评分卡片中增加 Safety 维度的展示，包括子维度分数和 feedback 文本。

**7. 更新测试。** 修改 golden test suite 中的预期分数，因为新增维度会改变 overall_score 的计算结果。同时为 SafetyEvaluator 编写单元测试。

## 代码依据

- `app/evaluators/base.py:32-373` — BaseEvaluator 抽象基类，新评估器需继承此类
- `app/graphs/evaluation_graph.py:480-487` — EVALUATOR_CLASSES 注册字典，需添加 safety 条目
- `app/graphs/evaluation_graph.py:50-69` — EvaluationState TypedDict，需添加 safety_score 字段
- `app/graphs/evaluation_graph.py:221-290` — aggregate_results 聚合逻辑，需纳入 safety 维度
- `app/core/config.py:136-143` — EVAL_DIMENSION_WEIGHTS 权重配置，需添加 safety 并重新归一化
- `app/graphs/evaluation_graph.py:113-148` — evaluate_planning 节点实现模式参考

## 回答要点

- 新建 safety_evaluator.py 继承 BaseEvaluator，定义 prompt、子维度和权重
- schemas.py 添加 SafetyScore 模型并在 OverallEvaluation 中注册
- config.py 权重配置需重新归一化，确保七维度权重之和为 1.0
- evaluation_graph.py 需改三处：State、EvaluatorClasses、aggregate_results
- 前端需同步展示新维度的雷达图和评分卡片
- 测试需更新 golden test 预期分数

## 常见追问

**Q: 权重重新归一化有什么注意事项？**

A: 有两种策略：(1) 等比缩减——所有原维度权重乘以 (1 - safety_weight)，保持相对比例不变；(2) 从最大权重维度扣减——减少 planning/tactical 各 0.03。推荐策略 1，因为它不改变现有维度间的相对重要性，对已有评估结果的影响最小。需要注意的是，权重变更后所有历史评估的 overall_score 不可直接对比，应在数据库中记录权重版本号。

**Q: Safety 评估和内容安全审核有什么区别？**

A: 内容安全审核通常是规则驱动的关键词/模式匹配，速度快但召回率有限。Safety Evaluator 是 LLM-as-judge 的语义理解，能识别隐晦的有害内容（如诱导性建议、隐性偏见），但成本更高、延迟更大。实际部署中建议两者结合：先过规则过滤，再用 LLM judge 精评。

## 相关题目

- [Q162](../answers/Q162-Planning低分排查.md)
- [Q171](../answers/Q171-extract-tool-calls.md)
