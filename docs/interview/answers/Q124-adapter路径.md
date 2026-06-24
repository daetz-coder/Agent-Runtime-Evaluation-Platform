# Q124: 三种 adapter 的安装/导入路径是什么？`app/adapters` 和 `sdk/adapters` 的关系？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q124 |
| 分类 | SDK 与零侵入接入 |
| 难度 | ★ |

## 问题

三种 adapter 的安装/导入路径是什么？`app/adapters` 和 `sdk/adapters` 的关系？

## 参考答案

围绕 adapter 路径：镜像关系；SDK 可独立 pip 面试回答应先说业务场景，再落到 app/adapters/ 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。sdk/ 可独立使用，三种 adapter 映射框架事件到 14 种 ActionType，EVAL_BATCH_SIZE 控制批量 flush。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。

## 代码依据

- `app/adapters/`
- `sdk/adapters/`
- `app/graphs/evaluation_graph.py`

## 回答要点

- adapter 路径：镜像关系
- 代码入口：app/adapters/
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「adapter 路径」最先看哪段代码？**

A: 打开 app/adapters/，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 adapter 路径？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q123](../answers/Q123-零侵入SDK.md)
- [Q125](../answers/Q125-LangGraph兼容性.md)
