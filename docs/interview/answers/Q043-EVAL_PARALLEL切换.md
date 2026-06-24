# Q43: `EVAL_PARALLEL=True/False` 切换时，行为差异是什么？什么场景下应该用串行？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q043 |
| 分类 | LangGraph 与工作流编排 |
| 难度 | ★ |

## 问题

`EVAL_PARALLEL=True/False` 切换时，行为差异是什么？什么场景下应该用串行？

## 参考答案

围绕 EVAL_PARALLEL：True 走 evaluate_parallel；False 可走 StateGraph 面试回答应先说业务场景，再落到 app/core/config.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。LangGraph 同时服务评估 workflow（evaluation_graph.py）与 Wiki Agent（wiki_agent/agent/graph.py），但生产评估并行走 evaluate_parallel。若涉及排错，先看 trajectory 是否含成对 tool_call/tool_result 与 retrieved_docs 字段。

## 代码依据

- `app/core/config.py`
- `app/services/evaluation_service.py`
- `app/graphs/evaluation_graph.py`

## 回答要点

- EVAL_PARALLEL：True 走 evaluate_parallel
- 代码入口：app/core/config.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「EVAL_PARALLEL」最先看哪段代码？**

A: 打开 app/core/config.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 EVAL_PARALLEL？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q042](../answers/Q042-串行图与并行gather.md)
- [Q044](../answers/Q044-State合并冲突.md)
