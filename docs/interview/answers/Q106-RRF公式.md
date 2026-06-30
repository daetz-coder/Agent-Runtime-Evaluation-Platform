# Q106: 请解释 RRF（Reciprocal Rank Fusion）公式，k=60 的含义是什么？

## 元信息

| 字段 | 内容 |
|------|------|
| 编号 | Q106 |
| 分类 | RAG 与检索质量 |
| 难度 | ★★★ |

## 问题

请解释 RRF（Reciprocal Rank Fusion）公式，k=60 的含义是什么？

## 参考答案

RRF（Reciprocal Rank Fusion）是一种无需归一化即可融合多个排序列表的算法，核心思想是用排名的倒数作为分数，而非依赖原始相似度分数。

**RRF 公式。** 对于一个文档 d，它在某个检索列表中排名为 rank（从 0 开始），其 RRF 分数贡献为 `1 / (k + rank + 1)`。如果该文档出现在多个检索列表中，分数累加。完整公式为：

```
RRF_score(d) = Σ 1 / (k + rank_i + 1)
```

其中 `rank_i` 是文档 d 在第 i 个检索列表中的 0-indexed 位置，k 是平滑常数。

**项目中的实现。** `search_tools.py:75-104` 中的 `_rrf_merge` 函数接收 `semantic_results` 和 `keyword_results` 两个列表，默认 `rrf_k=60`。核心计算逻辑在第 91-96 行：遍历每个列表，按 `1.0 / (rrf_k + rank + 1)` 累加到 `rrf_scores` 字典中。例如，一个文档在语义搜索中排名第 0、在关键词搜索中排名第 3，其 RRF 分数 = `1/(60+0+1) + 1/(60+3+1) = 1/61 + 1/64 ≈ 0.0164 + 0.0156 = 0.0320`。

**k=60 的含义。** k 是一个控制排名衰减陡峭程度的常数。k 越大，排名靠前和靠后的文档之间的分数差异越小（曲线更平缓）；k 越小，排名靠前的文档优势越大（曲线更陡峭）。以 k=60 为例：rank-0 的贡献是 1/61 ≈ 0.0164，rank-10 的贡献是 1/71 ≈ 0.0141，差距约 14%；而如果 k=10，rank-0 贡献 1/11 ≈ 0.0909，rank-10 贡献 1/21 ≈ 0.0476，差距达 48%。k=60 来自 Cormack、Clarke 和 Butt 的原始论文（SIGIR 2009），是被广泛采用的经验值，在大多数检索场景下表现稳定。

**为什么使用 RRF 而非加权分数融合？** 语义搜索返回的是 Milvus 向量余弦相似度（范围 0-1），BM25 返回的是 Okapi BM25 分数（无固定范围，取决于语料库大小和词频分布）。两者的分数尺度完全不同，直接加权融合需要先做 min-max 归一化或 z-score 标准化，而这些归一化方法对异常值敏感且引入额外参数。RRF 完全不依赖原始分数，只使用排名信息，从根本上避免了尺度不匹配问题。

**完整的混合搜索流水线。** `hybrid_search` 函数（`search_tools.py:107-128`）实现了三阶段检索：

1. **召回阶段**：`semantic_search`（Milvus COSINE 相似度，`search_tools.py:19-56`）和 `keyword_search`（BM25 Okapi + jieba 分词，`search_tools.py:59-72`）各自召回 `limit * RERANK_CANDIDATE_MULTIPLIER` 个候选。语义搜索内部会按 path 去重（第 37-50 行），同一页面的多个 chunk 只保留最高分，避免同一文档因多个 chunk 出现而获得不公平的 RRF 累加。

2. **融合阶段**：`_rrf_merge` 将两个列表按 RRF 合并为一个统一排序。

3. **重排阶段**：`rerank_results`（`reranker.py:129-157`）使用 BGE Cross-Encoder 对候选做精排，输出最终 top-k 结果。Cross-Encoder 对 query-document pair 做联合编码，比 Bi-Encoder 的双塔模型更精准，但计算成本更高，所以只在候选集上做精排而非全库扫描。

**jieba 分词的作用。** BM25 搜索依赖分词质量。`bm25_index.py:81-84` 中的 `_tokenize` 使用 `jieba.lcut()` 做中文分词，过滤停用词和单字 token（`len(t) > 1`），确保关键词检索对中文内容有效。停用词列表（`bm25_index.py:42-78`）包含常见的中文虚词如"的"、"了"、"在"等。

**分块参数。** 文档入库时使用 `chunk_markdown`（`chunker.py:45-67`）分块，默认 `chunk_size=500`、`chunk_overlap=50`，使用 LangChain 的 `RecursiveCharacterTextSplitter`，按双换行、单换行、句号、中文标点等分层分隔符切分，保证语义完整性。

## 代码依据

- `app/wiki_agent/agent/tools/search_tools.py:75-104` — _rrf_merge 函数，rrf_k=60，按 1/(k+rank+1) 累加
- `app/wiki_agent/agent/tools/search_tools.py:91-96` — RRF 核心计算，遍历两个列表累加分数
- `app/wiki_agent/agent/tools/search_tools.py:107-128` — hybrid_search 三阶段流水线：召回→RRF 融合→Cross-Encoder 重排
- `app/wiki_agent/agent/tools/search_tools.py:19-56` — semantic_search，Milvus COSINE，按 path 去重
- `app/wiki_agent/agent/tools/search_tools.py:59-72` — keyword_search，BM25 Okapi + jieba
- `app/wiki_agent/agent/tools/bm25_index.py:81-84` — _tokenize 使用 jieba.lcut()，过滤停用词和单字
- `app/wiki_agent/agent/tools/bm25_index.py:42-78` — 中文停用词列表
- `app/wiki_agent/agent/tools/reranker.py:129-157` — rerank_results 使用 BGE Cross-Encoder 精排
- `app/wiki_agent/agent/tools/chunker.py:45-67` — chunk_markdown，chunk_size=500, chunk_overlap=50

## 回答要点

- RRF 公式：score += 1/(k + rank + 1)，rank 从 0 开始，多列表分数累加
- k=60 是平滑常数，控制排名衰减陡峭度，来自 Cormack et al. SIGIR 2009 原始论文
- k 越大曲线越平缓（top 和 bottom 差异小），k 越小 top 优势越大
- 使用 RRF 而非加权融合的根本原因：避免向量相似度与 BM25 分数的尺度不匹配
- 三阶段流水线：语义+BM25 召回 → RRF 融合 → BGE Cross-Encoder 精排
- semantic_search 按 path 去重防止同一文档多个 chunk 被不公平累加
- jieba 分词 + 停用词过滤保证中文 BM25 检索质量

## 常见追问

**Q: k 值能否调优？项目中是否支持配置？**

A: 当前代码中 `rrf_k=60` 是硬编码的默认参数（`search_tools.py:79`），没有暴露到配置文件。理论上可以做成 `settings.RRF_K` 配置项。k 的调优通常通过在标注数据集上做 grid search（如 k=10,30,60,100），选择 MAP 或 NDCG 最优的值。k=60 在多数场景下已经足够好，过度调优的收益有限。

**Q: 如果语义搜索不可用（Milvus 未部署），混合搜索如何降级？**

A: `semantic_search`（第 31-32 行）检查 `store.available`，如果 Milvus 不可用，直接 fallback 到 `keyword_search`。此时 `_rrf_merge` 只收到 keyword_results 一个列表，RRF 退化为单列表排序，结果等价于纯 BM25 搜索。

**Q: Cross-Encoder 重排失败怎么办？**

A: `rerank_results`（`reranker.py:143-146`）捕获重排异常，fallback 到 RRF 原始排序并取 top-k。此外，如果 `RERANK_ENABLED=False` 或模型加载失败（`model is None`），也直接返回 RRF 排序的前 k 个结果。这保证了流水线的鲁棒性。

**Q: 为什么 semantic_search 召回 limit*3 个候选？**

A: 第 35 行 `store.search(embedding, limit=limit * 3)` 多召回是为了在 path 去重后仍有足够的候选。同一页面可能有多个 chunk 命中，去重后实际文档数会少于召回数。多召回确保去重后仍有足够多样性。`hybrid_search` 中的 `recall_limit = max(limit * RERANK_CANDIDATE_MULTIPLIER, limit * 2)`（第 122 行）也是同理——给 RRF 融合和 Cross-Encoder 重排提供足够大的候选池。

**Q: RRF 与 Reciprocal Rank 有什么区别？**

A: Reciprocal Rank（RR）只考虑第一个正确结果的排名（1/rank），用于单查询评估。Reciprocal Rank Fusion（RRF）是对多个排序列表中每个文档的排名倒数求和，用于融合多个检索系统的结果。RRF 是 RR 的泛化版本。

## 相关题目

- [Q105](../answers/Q105-Milvus降级BM25.md)
- [Q107](../answers/Q107-RRF-vs加权.md)
- [Q109](../answers/Q109-语义搜索去重.md)
- [Q110](../answers/Q110-BM25参数.md)
