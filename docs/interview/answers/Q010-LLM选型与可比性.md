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

>  Q: 默认 LLM 为什么选 DeepSeek？
>  A: 三个原因——
>     1. 成本：$0.14/M input tokens，是 GPT-4o 的 1/18
>     2. 中文能力：DeepSeek 对中文 prompt 理解好，评估 prompt 含中文
>     3. 速度：flash 模型推理快，6 个评估器并行 ~15s 出结果
>
>  Q: 切换 Provider 时如何保证可比性？
>  A: 三层机制——
>     1. Prompt 不变：所有 Provider 共用同一套评估 Prompt，只换底层模型
>     2. temperature=0：消除随机性，同模型多次评估结果一致
>     3. Monotonicity Benchmark：换模型后重跑，分数必须单调递减
>     4. Consensus 共识：多模型独立评分，std_score 高则告警
>
>  Q: 自评偏见怎么办？
>  A: 如果 Agent 和 Judge 用同一个模型（都是 DeepSeek），
>     可能对 DeepSeek 风格的输出更宽容。解决方案：
>     - 用不同模型做 Judge（Agent 用 DeepSeek，Judge 用 GPT-4o）
>
>- 跑 Consensus，如果 std 低则说明不存在偏见



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
