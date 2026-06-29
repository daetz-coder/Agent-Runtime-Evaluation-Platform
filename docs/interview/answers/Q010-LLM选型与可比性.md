# Q10: 默认 LLM 为什么选 DeepSeek？切换 OpenAI / Anthropic / 智谱 / 通义时，评估结果的可比性如何保证？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q010 |
| 分类 | 项目理解与动机 |
| 难度 | ★ |

## 问题

默认 LLM 为什么选 DeepSeek？切换 OpenAI / Anthropic / 智谱 / 通义时，评估结果的可比性如何保证？

## 参考答案

默认 DeepSeek deepseek-v4-flash 通过 ChatOpenAI + DEEPSEEK_BASE_URL，成本与速度平衡。BaseEvaluator._get_default_llm 按 DEFAULT_LLM_PROVIDER 切换 anthropic/deepseek/glm/qwen/openai，均 temperature=0。可比性：换模型应重跑 monotonicity benchmark 与 REFERENCE_SCORES 对齐；benchmark_multimodel.py 可对比不同 Judge 排序一致性；consensus.py 的 std_score 高则告警。

## 代码依据

- `app/evaluators/base.py`
- `app/core/config.py`
- `app/evaluators/consensus.py`

## 回答要点

- temperature=0 保证 Judge 稳定
- 多 provider 统一 BaseEvaluator 入口
- 换模型需重标 benchmark
- consensus 多模型降低单模型偏见

## 常见追问

**Q: 自评偏见？**

A: Judge 与 Agent 同模型可能偏宽松，用不同模型或 consensus。

**Q: 如何保证可比？**

A: 固定 prompt 版本 + monotonicity 回归 + 记录 model 版本。

## 相关题目

- [Q009](../answers/Q009-为何选FastAPI.md)
- [Q011](../answers/Q011-Milvus选型.md)
