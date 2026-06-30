# Q054: 什么是 LLM-as-Judge？相比传统 rubric + 人工打分，优势和局限分别是什么？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q054 |
| 分类 | LLM-as-Judge 评估体系 |
| 难度 | ★★ |

## 问题

什么是 LLM-as-Judge？相比传统 rubric + 人工打分，优势和局限分别是什么？

## 参考答案

LLM-as-Judge 是一种用大语言模型代替人类评审员来评估 Agent 行为的方法。具体做法是：将结构化评分标准（rubric）和待评估的轨迹数据组装成 prompt，发送给 LLM，由 LLM 输出结构化分数和反馈文本。在本项目中，每个评估维度（planning、tactical 等）都有独立的 prompt 模板和评分 rubric，Judge LLM 根据 rubric 对轨迹打分。

**优势方面**：(1) **可扩展性强**——6 个维度可同时评估数千条轨迹，不受人工评审时间瓶颈限制。`evaluate_parallel()`（`evaluation_graph.py:422-477`）通过 `asyncio.gather`（第 456 行）并发调用 6 个评估器，单次评估约 15 秒完成。(2) **一致性高**——所有 Judge LLM 的 temperature 设为 0（`base.py:58,65,74,82,87`），对相同输入产生确定性输出，消除了人工评分中的主观波动。(3) **可解释性好**——Judge 不仅输出分数，还生成 feedback 文本和 suggestions 列表（如 `planning_evaluator.py:62-65` 的输出格式），为改进提供直接依据。(4) **成本低**——通过 Redis 缓存 LLM 调用结果（`base.py:294-372`，`_invoke_llm_cached`），重复评估几乎零成本。

**局限方面**：(1) **Judge 自身偏见**——LLM 存在冗长偏好（verbosity bias，倾向给长文本高分）和位置偏好（position bias），可能偏离真实质量。(2) **领域盲区**——Judge LLM 无法评估它不具备知识的领域，如高度专业的工程细节。(3) **JSON 解析失败**——Judge 输出未必总是合法 JSON，需要回退策略（`planning_evaluator.py:204-225` 的 `_parse_scores` 在解析失败时返回默认 50 分）。(4) **缺乏真值校准**——没有 ground truth 时无法判断 Judge 偏差方向。

**本项目的缓解措施**：(1) **单调性基准测试**——`app/benchmarks/monotonicity.py:35-43` 的 `check_monotonicity()` 验证分数是否随轨迹质量单调递减，用于校准 Judge 行为。(2) **多模型共识**——`app/evaluators/consensus.py` 支持多个 LLM 同时评分，通过共识机制降低单模型偏差。(3) **Judge 透明面板**——`base.py:42-48` 的 `get_last_judge_raw()` 和 `get_judge_raw_history()` 保存每次 LLM 调用的原始 prompt 和 response，供人工抽检。

## 代码依据

- `app/evaluators/base.py:50-88` — _get_default_llm，temperature=0，支持 5 个 LLM 提供商
- `app/evaluators/base.py:294-372` — _invoke_llm_cached，Redis 缓存 LLM 调用
- `app/evaluators/base.py:42-48` — get_last_judge_raw / get_judge_raw_history，Judge 原始数据透明
- `app/evaluators/planning_evaluator.py:18-66` — PLANNING_EVALUATION_PROMPT，中文 rubric prompt 模板
- `app/evaluators/planning_evaluator.py:204-225` — _parse_scores，JSON 解析失败时回退到默认分数
- `app/benchmarks/monotonicity.py:35-43` — check_monotonicity，单调性校准基准
- `app/services/evaluation_service.py:430-448` — 并行评估通过 asyncio.gather 执行

## 回答要点

- LLM-as-Judge = 用 LLM 按结构化 rubric 评估 Agent 行为并输出分数+反馈
- 优势：可扩展（并发评估）、一致（temperature=0）、可解释（输出 feedback）、低成本（Redis 缓存）
- 局限：Judge 偏见（冗长/位置偏好）、领域盲区、JSON 解析失败、缺乏真值校准
- 缓解：单调性基准测试校准、多模型共识降偏差、Judge 原始数据透明供人工抽检

## 常见追问

**Q: temperature=0 是否真的能保证完全确定性输出？**

A: 不完全能。temperature=0 使采样策略变为 greedy decoding，大幅降低随机性，但在分布式推理环境中，浮点运算的非确定性（如 CUDA atomicAdd）仍可能导致微小差异。此外，LLM 提供商的 API 层可能有负载均衡和版本切换。因此 temperature=0 是"近似确定性"而非"绝对确定性"。本项目通过 `_invoke_llm_cached`（`base.py:294-372`）的 Redis 缓存机制进一步保证：相同 prompt hash 对应相同结果。

**Q: 多模型共识具体怎么实现？**

A: `app/evaluators/consensus.py` 让多个 LLM（如 DeepSeek + Qwen + GLM）各自独立评分，然后取中位数或加权平均作为最终分数。这样即使单个模型有系统性偏差，共识结果也能趋向准确。

## 相关题目

- [Q061](../answers/Q061-Planning-prompt.md)
- [Q040](../answers/Q040-评估工作流.md)
