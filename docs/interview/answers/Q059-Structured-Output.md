# Q59: 是否考虑过 Structured Output / Function Calling 来约束 Judge 输出格式？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q059 |
| 分类 | LLM-as-Judge 评估体系 |
| 难度 | ★ |

## 问题

是否考虑过 Structured Output / Function Calling 来约束 Judge 输出格式？

## 参考答案

Q59 与 Structured Output 相关。可用 with_structured_output 替代手工 parse Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。六维 Evaluator 继承 BaseEvaluator，temperature=0，JSON 解析失败时各子维 fallback 50 分。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。

## 代码依据

- `app/evaluators/planning_evaluator.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- Structured Output：可用 with_structured_output 替代手工 parse
- 代码入口：app/evaluators/planning_evaluator.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「Structured Output」最先看哪段代码？**

A: 打开 app/evaluators/planning_evaluator.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 Structured Output？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q058](../answers/Q058-JSON抽取漏洞.md)
- [Q060](../answers/Q060-consensus-std-score.md)
