# Q67: 一次完整六维评估大约消耗多少 token？成本如何估算？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q067 |
| 分类 | LLM-as-Judge 评估体系 |
| 难度 | ★ |

## 问题

一次完整六维评估大约消耗多少 token？成本如何估算？

## 参考答案

围绕 token 成本：六维各一次 LLM；轨迹长度主导；并行不省 token 面试回答应先说业务场景，再落到 app/evaluators/ 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。六维 Evaluator 继承 BaseEvaluator，temperature=0，JSON 解析失败时各子维 fallback 50 分。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。

## 代码依据

- `app/evaluators/`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- token 成本：六维各一次 LLM
- 代码入口：app/evaluators/
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「token 成本」最先看哪段代码？**

A: 打开 app/evaluators/，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 token 成本？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q066](../answers/Q066-prompt版本管理.md)
- [Q068](../answers/Q068-成本追踪.md)
