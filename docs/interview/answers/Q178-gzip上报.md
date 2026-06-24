# Q178: 实现 trajectory 的 gzip 压缩上报，前后端各改什么？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q178 |
| 分类 | 编码与现场设计题 |
| 难度 | ★ |

## 问题

实现 trajectory 的 gzip 压缩上报，前后端各改什么？

## 参考答案

围绕 gzip 上报：Content-Encoding gzip 解压 面试回答应先说业务场景，再落到 sdk/collector.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。改动 Evaluator 需同步 app/models/schemas.py、evaluators/__init__.py、evaluation_graph 注册与 aggregate WEIGHTS。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。

## 代码依据

- `sdk/collector.py`
- `app/api/`
- `app/graphs/evaluation_graph.py`

## 回答要点

- gzip 上报：Content-Encoding gzip 解压
- 代码入口：sdk/collector.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「gzip 上报」最先看哪段代码？**

A: 打开 sdk/collector.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 gzip 上报？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q177](../answers/Q177-采样率上报.md)
- [Q179](../answers/Q179-可执行性子维.md)
