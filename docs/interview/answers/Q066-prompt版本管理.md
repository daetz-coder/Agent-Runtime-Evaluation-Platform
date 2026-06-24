# Q66: 评估 prompt 的版本管理策略是什么？改了 prompt 如何对比历史评估结果？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q066 |
| 分类 | LLM-as-Judge 评估体系 |
| 难度 | ★ |

## 问题

评估 prompt 的版本管理策略是什么？改了 prompt 如何对比历史评估结果？

## 参考答案

问题「评估 prompt 的版本管理策略是什么？改了 prompt 如何对比历史评估结果？」考察 prompt 版本管理。prompt 常量化+git tag；评估记录 prompt_version 六维 Evaluator 继承 BaseEvaluator，temperature=0，JSON 解析失败时各子维 fallback 50 分。 首要读 app/evaluators/，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。

## 代码依据

- `app/evaluators/`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- prompt 版本管理：prompt 常量化+git tag
- 代码入口：app/evaluators/
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「prompt 版本管理」最先看哪段代码？**

A: 打开 app/evaluators/，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 prompt 版本管理？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q065](../answers/Q065-Prompt-Injection.md)
- [Q067](../answers/Q067-token成本.md)
