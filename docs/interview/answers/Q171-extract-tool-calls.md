# Q171: 请阅读 `BaseEvaluator._extract_tool_calls`，说明它如何从 trajectory 提取工具调用对。

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q171 |
| 分类 | 编码与现场设计题 |
| 难度 | ★★ |

## 问题

请阅读 `BaseEvaluator._extract_tool_calls`，说明它如何从 trajectory 提取工具调用对。

## 参考答案

问题「请阅读 `BaseEvaluator._extract_tool_calls`，说明它如何从 trajectory 提取工具调用对。」考察 _extract_tool_calls。顺序扫描 tool_call 配 tool_result 改动 Evaluator 需同步 app/models/schemas.py、evaluators/__init__.py、evaluation_graph 注册与 aggregate WEIGHTS。 首要读 app/evaluators/base.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。

## 代码依据

- `app/evaluators/base.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- _extract_tool_calls：顺序扫描 tool_call 配 tool_result
- 代码入口：app/evaluators/base.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「_extract_tool_calls」最先看哪段代码？**

A: 打开 app/evaluators/base.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 _extract_tool_calls？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q170](../answers/Q170-JSON-parse错误.md)
- [Q172](../answers/Q172-evaluate-parallel.md)
