# Q54: 什么是 LLM-as-Judge？相比传统 rubric + 人工打分，优势和局限分别是什么？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q054 |
| 分类 | LLM-as-Judge 评估体系 |
| 难度 | ★★ |

## 问题

什么是 LLM-as-Judge？相比传统 rubric + 人工打分，优势和局限分别是什么？

## 参考答案

问题「什么是 LLM-as-Judge？相比传统 rubric + 人工打分，优势和局限分别是什么？」考察 LLM-as-Judge。ChatPromptTemplate + temperature=0 + JSON 分数 六维 Evaluator 继承 BaseEvaluator，temperature=0，JSON 解析失败时各子维 fallback 50 分。 首要读 app/evaluators/base.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及接入，说明 sdk/adapters/ 三种 adapter 的场景选择。

## 代码依据

- `app/evaluators/base.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- LLM-as-Judge：ChatPromptTemplate + temperature=0 + JSON 分数
- 代码入口：app/evaluators/base.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「LLM-as-Judge」最先看哪段代码？**

A: 打开 app/evaluators/base.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 LLM-as-Judge？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q053](../answers/Q053-interrupt机制.md)
- [Q055](../answers/Q055-temperature为零.md)
