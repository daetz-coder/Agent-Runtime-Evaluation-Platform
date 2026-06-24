# Q57: JSON 解析失败时 fallback 到 50 分，这个策略合理吗？有没有更好的降级方案？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q057 |
| 分类 | LLM-as-Judge 评估体系 |
| 难度 | ★★★ |

## 问题

JSON 解析失败时 fallback 到 50 分，这个策略合理吗？有没有更好的降级方案？

## 参考答案

问题「JSON 解析失败时 fallback 到 50 分，这个策略合理吗？有没有更好的降级方案？」考察 JSON fallback 50。解析失败各子维 50；保守中性；可改 retry 或 structured output 六维 Evaluator 继承 BaseEvaluator，temperature=0，JSON 解析失败时各子维 fallback 50 分。 首要读 app/evaluators/planning_evaluator.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。

## 代码依据

- `app/evaluators/planning_evaluator.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- JSON fallback 50：解析失败各子维 50
- 代码入口：app/evaluators/planning_evaluator.py
- 各 Evaluator _parse_scores fallback 50
- content.find('{') 抽取 JSON
- 可改 structured output

## 常见追问

**Q: 「JSON fallback 50」最先看哪段代码？**

A: 打开 app/evaluators/planning_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 JSON fallback 50？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q056](../answers/Q056-自评偏见.md)
- [Q058](../answers/Q058-JSON抽取漏洞.md)
