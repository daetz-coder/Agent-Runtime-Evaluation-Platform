# Q58: 如何从 LLM 响应中抽取 JSON？`content.find("{")` 这种方法有什么漏洞？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q058 |
| 分类 | LLM-as-Judge 评估体系 |
| 难度 | ★ |

## 问题

如何从 LLM 响应中抽取 JSON？`content.find("{")` 这种方法有什么漏洞？

## 参考答案

围绕 JSON 抽取漏洞：find/rfind 可能被嵌套 JSON 或 markdown 误导 面试回答应先说业务场景，再落到 app/evaluators/planning_evaluator.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。六维 Evaluator 继承 BaseEvaluator，temperature=0，JSON 解析失败时各子维 fallback 50 分。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。

## 代码依据

- `app/evaluators/planning_evaluator.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- JSON 抽取漏洞：find/rfind 可能被嵌套 JSON 或 markdown 误导
- 代码入口：app/evaluators/planning_evaluator.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「JSON 抽取漏洞」最先看哪段代码？**

A: 打开 app/evaluators/planning_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 JSON 抽取漏洞？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q057](../answers/Q057-JSON-fallback-50分.md)
- [Q059](../answers/Q059-Structured-Output.md)
