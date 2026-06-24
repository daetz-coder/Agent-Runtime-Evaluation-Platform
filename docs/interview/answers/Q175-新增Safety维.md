# Q175: 新增第七维 Evaluator「Safety」，评估 Agent 是否输出有害内容，需要改哪些文件？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q175 |
| 分类 | 编码与现场设计题 |
| 难度 | ★★ |

## 问题

新增第七维 Evaluator「Safety」，评估 Agent 是否输出有害内容，需要改哪些文件？

## 参考答案

围绕 新增 Safety 维：新 evaluator+schema+权重 面试回答应先说业务场景，再落到 app/evaluators/ 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。改动 Evaluator 需同步 app/models/schemas.py、evaluators/__init__.py、evaluation_graph 注册与 aggregate WEIGHTS。若涉及接入，说明 app/adapters/ 与 sdk/adapters/ 三种 adapter 的场景选择。

## 代码依据

- `app/evaluators/`
- `app/graphs/evaluation_graph.py`
- `app/graphs/evaluation_graph.py`

## 回答要点

- 新增 Safety 维：新 evaluator+schema+权重
- 代码入口：app/evaluators/
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「新增 Safety 维」最先看哪段代码？**

A: 打开 app/evaluators/，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 新增 Safety 维？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q174](../answers/Q174-RRF手算.md)
- [Q176](../answers/Q176-效率Evaluator.md)
