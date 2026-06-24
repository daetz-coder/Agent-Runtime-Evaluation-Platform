# Q109: 语义检索按 path 去重保留最高分 chunk——为什么去重？会丢失信息吗？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q109 |
| 分类 | RAG 与检索质量 |
| 难度 | ★ |

## 问题

语义检索按 path 去重保留最高分 chunk——为什么去重？会丢失信息吗？

## 参考答案

围绕 path 去重：同 path 保留最高分 chunk 防刷屏 面试回答应先说业务场景，再落到 app/wiki_agent/agent/tools/search_tools.py 的实现细节与配置项（app/core/config.py 中 EVAL_PARALLEL、EVAL_BATCH_SIZE 等）。Wiki 侧 hybrid_search 用 Milvus 语义 + jieba BM25，RRF k=60 融合；检索步骤需 record_retrieval 供 RetrievalEvaluator。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。

## 代码依据

- `app/wiki_agent/agent/tools/search_tools.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- path 去重：同 path 保留最高分 chunk 防刷屏
- 代码入口：app/wiki_agent/agent/tools/search_tools.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「path 去重」最先看哪段代码？**

A: 打开 app/wiki_agent/agent/tools/search_tools.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 path 去重？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q108](../answers/Q108-jieba-BM25.md)
- [Q110](../answers/Q110-top-k调参.md)
