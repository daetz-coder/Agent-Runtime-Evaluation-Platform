# Q172: 阅读 `evaluate_parallel()`，解释并发控制和异常处理逻辑。

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q172 |
| 分类 | 编码与现场设计题 |
| 难度 | ★ |

## 问题

阅读 `evaluate_parallel()`，解释并发控制和异常处理逻辑。

## 参考答案

围绕 evaluate_parallel：asyncio.gather 六 Evaluator 异常返 0 面试回答应先说业务场景，再落到 app/graphs/evaluation_graph.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。改动 Evaluator 需同步 app/models/schemas.py、evaluators/__init__.py、evaluation_graph 注册与 aggregate WEIGHTS。若涉及可靠性，提 monotonicity benchmark 容差 +0.05 与 ReplanEvaluator 无 missed 时满分 100 的规则。

## 代码依据

- `app/graphs/evaluation_graph.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- evaluate_parallel：asyncio.gather 六 Evaluator 异常返 0
- 代码入口：app/graphs/evaluation_graph.py
- asyncio.gather 六任务
- 单维异常返回 overall 0
- EvaluationService 生产默认路径

## 常见追问

**Q: 「evaluate_parallel」最先看哪段代码？**

A: 打开 app/graphs/evaluation_graph.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 evaluate_parallel？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q171](../answers/Q171-extract-tool-calls.md)
- [Q173](../answers/Q173-instrument-langgraph.md)
