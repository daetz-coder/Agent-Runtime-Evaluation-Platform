# Q11: 向量库为什么用 Milvus Lite 而不是 Chroma、FAISS、pgvector？生产环境你会怎么换？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q011 |
| 分类 | 项目理解与动机 |
| 难度 | ★ |

## 问题

向量库为什么用 Milvus Lite 而不是 Chroma、FAISS、pgvector？生产环境你会怎么换？

## 参考答案

Wiki Agent 用 Milvus Lite 嵌入式向量库，schema 含 path/chunk/title/embedding（见 vector store 模块），配合 BAAI/bge-small-zh-v1.5（512 维）。选型理由：本地 Demo 零运维、与 hybrid_search 集成简单。Milvus 不可用时 semantic_search 降级 BM25（search_tools.py）。生产可换 Milvus 集群、pgvector 或 Qdrant，只需替换 embedding 与 store 层，RRF 融合逻辑可保留。

>其实 Chroma 也支持 Metadata，也能返回距离分数，因此我不用 Chroma 的原因并不是功能缺失。关键在于这个项目需要评估 Retrieval 过程本身，而不仅是获取最终 TopK 文档。我们希望把向量召回、BM25 召回、RRF 融合和 Evidence 构建分别记录到 Trajectory 中，这样 RetrievalEvaluator 才能分析“为什么检索成功”或者“为什么检索失败”。因此项目采用 Milvus Lite 作为底层 ANN 引擎，而把检索融合逻辑保留在自己的 hybrid_search 中。这样可观测性更强，也更符合 Agent Runtime Evaluation 平台的目标。



## 代码依据

- `app/wiki_agent/agent/tools/search_tools.py`
- `app/wiki_agent/seed/knowledge/platform/vector-index.md`
- `app/graphs/evaluation_graph.py`

## 回答要点

- Milvus Lite 适合本地 Demo
- BGE 中文小模型 512 维
- 不可用降级 BM25
- 生产换分布式 Milvus 或 pgvector

## 常见追问

**Q: 为什么不用 Chroma？**

A: Milvus 生态与规模扩展更好；Lite 模式满足 Demo。

**Q: 512 维够吗？**

A: 中文 wiki 场景够用；长文档可换 bge-large。

## 相关题目

- [Q010](../answers/Q010-LLM选型与可比性.md)
- [Q012](../answers/Q012-Vue前端选型.md)
