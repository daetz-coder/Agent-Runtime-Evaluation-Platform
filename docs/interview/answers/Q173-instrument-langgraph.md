# Q173: 阅读 `instrument_langgraph` 的核心包装逻辑，说明如何拦截节点执行。

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q173 |
| 分类 | 编码与现场设计题 |
| 难度 | ★ |

## 问题

阅读 `instrument_langgraph` 的核心包装逻辑，说明如何拦截节点执行。

## 参考答案

Q173 与 instrument_langgraph 相关。wrap 节点函数 record 前后 Wiki Demo 在 app/wiki_agent/ 提供端到端样例；外部 Agent 通过 sdk/collector.py 上报同样 schema。改动 Evaluator 需同步 app/models/schemas.py、evaluators/__init__.py、evaluation_graph 注册与 aggregate WEIGHTS。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。

## 代码依据

- `sdk/adapters/langgraph.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- instrument_langgraph：wrap 节点函数 record 前后
- 代码入口：sdk/adapters/langgraph.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「instrument_langgraph」最先看哪段代码？**

A: 打开 sdk/adapters/langgraph.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 instrument_langgraph？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q172](../answers/Q172-evaluate-parallel.md)
- [Q174](../answers/Q174-RRF手算.md)
