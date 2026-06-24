# Q108: jieba 分词 + 停用词对 BM25 的影响？英文内容检索效果如何？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q108 |
| 分类 | RAG 与检索质量 |
| 难度 | ★ |

## 问题

jieba 分词 + 停用词对 BM25 的影响？英文内容检索效果如何？

## 参考答案

问题「jieba 分词 + 停用词对 BM25 的影响？英文内容检索效果如何？」考察 jieba BM25。中文分词；英文靠 BM25 仍可用但弱于 semantic Wiki 侧 hybrid_search 用 Milvus 语义 + jieba BM25，RRF k=60 融合；检索步骤需 record_retrieval 供 RetrievalEvaluator。 首要读 app/wiki_agent/agent/tools/search_tools.py，并结合 evaluation_graph.py 理解评估如何消费 trajectory。若涉及 RAG，强调 hybrid_search 的 RRF k=60 与 record_retrieval 写入 ActionType.RETRIEVAL。

## 代码依据

- `app/wiki_agent/agent/tools/search_tools.py`
- `app/graphs/evaluation_graph.py`
- `app/evaluators/base.py`

## 回答要点

- jieba BM25：中文分词
- 代码入口：app/wiki_agent/agent/tools/search_tools.py
- 与六维 LLM-as-Judge 评估链路相关
- 轨迹 schema 见 app/models/action_types.py

## 常见追问

**Q: 「jieba BM25」最先看哪段代码？**

A: 打开 app/wiki_agent/agent/tools/search_tools.py，再对照 app/graphs/evaluation_graph.py 的数据流。

**Q: Demo 里如何验证 jieba BM25？**

A: 跑 Wiki Agent + EVAL_AUTO_RUN，或 sdk/collector finish(auto_run=True)。

**Q: 与 benchmark 关系？**

A: 改相关 Evaluator 后跑 app/benchmarks/monotonicity.py 看是否仍单调。

## 相关题目

- [Q107](../answers/Q107-RRF-vs加权.md)
- [Q109](../answers/Q109-path去重.md)
