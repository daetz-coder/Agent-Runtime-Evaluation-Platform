"""搜索工具 — 语义搜索、BM25 搜索、RRF 混合搜索"""

from __future__ import annotations

from app.wiki_agent.config import settings

# 缓存 embedding 模型
_embedding_model = None


def _get_embedding_model():
    """获取或加载 Embedding 模型（单例）"""
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL_PATH)
        except Exception as e:
            print(f"[搜索] Embedding 模型加载失败: {e}")
    return _embedding_model


def semantic_search(query: str, limit: int = 5) -> list[dict]:
    """语义搜索 — 基于向量相似度搜索

    Args:
        query: 搜索查询
        limit: 返回结果数量

    Returns:
        list[dict]: 搜索结果列表
    """
    try:
        import chromadb
        client = chromadb.PersistentClient(path=settings.CHROMA_DIR)
        collection = client.get_or_create_collection(
            name="wiki_knowledge",
            metadata={"hnsw:space": "cosine"},
        )

        # 生成查询向量
        embedding = _generate_embedding(query)

        # 向量搜索（多取一些，后续去重）
        results = collection.query(
            query_embeddings=[embedding],
            n_results=limit * 3,
            include=["documents", "metadatas", "distances"],
        )

        # 格式化结果并按文档去重（保留最高分的分块）
        seen_paths = {}
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                distance = results["distances"][0][i] if results["distances"] else 0
                score = 1 - distance
                path = metadata.get("path", doc_id)

                # 只保留每个文档的最高分分块
                if path not in seen_paths or score > seen_paths[path]["score"]:
                    seen_paths[path] = {
                        "path": path,
                        "title": metadata.get("title", ""),
                        "snippet": results["documents"][0][i][:200] if results["documents"] else "",
                        "score": score,
                        "search_type": "semantic",
                    }

        # 按分数排序，返回前 limit 个
        formatted = sorted(seen_paths.values(), key=lambda x: x["score"], reverse=True)
        return formatted[:limit]
    except Exception as e:
        print(f"[搜索] 语义搜索失败: {e}")
        # 降级到关键词搜索
        return keyword_search(query, limit)


def keyword_search(query: str, limit: int = 5) -> list[dict]:
    """BM25 搜索 — 基于 jieba 分词 + TF-IDF 加权的关键词检索

    Args:
        query: 搜索查询
        limit: 返回结果数量

    Returns:
        list[dict]: 搜索结果列表
    """
    from app.wiki_agent.agent.tools.bm25_index import get_bm25_index
    bm25 = get_bm25_index()
    return bm25.search(query, limit)


def hybrid_search(query: str, limit: int = 5) -> list[dict]:
    """混合搜索 — RRF（倒数秩融合）结合语义搜索和 BM25 搜索

    Args:
        query: 搜索查询
        limit: 返回结果数量

    Returns:
        list[dict]: 搜索结果列表（RRF 融合排序）
    """
    RRF_K = 60  # RRF 平滑常数

    # 获取两路搜索结果
    semantic_results = semantic_search(query, limit * 2)
    keyword_results = keyword_search(query, limit * 2)

    # 收集所有 path 对应的最佳结果（用于最终输出）
    best_result: dict[str, dict] = {}
    for r in semantic_results:
        if r["path"] not in best_result:
            best_result[r["path"]] = r
    for r in keyword_results:
        if r["path"] not in best_result:
            best_result[r["path"]] = r

    # RRF: score = sum(1 / (k + rank_i))
    rrf_scores: dict[str, float] = {}
    for rank, r in enumerate(semantic_results):
        rrf_scores.setdefault(r["path"], 0.0)
        rrf_scores[r["path"]] += 1.0 / (RRF_K + rank + 1)
    for rank, r in enumerate(keyword_results):
        rrf_scores.setdefault(r["path"], 0.0)
        rrf_scores[r["path"]] += 1.0 / (RRF_K + rank + 1)

    # 合并结果，按 RRF 分数排序
    merged = []
    for path, rrf_score in rrf_scores.items():
        entry = {**best_result[path], "score": rrf_score, "search_type": "hybrid"}
        merged.append(entry)

    merged.sort(key=lambda x: x["score"], reverse=True)
    return merged[:limit]


def _generate_embedding(text: str) -> list[float]:
    """生成文本的向量嵌入

    Args:
        text: 输入文本

    Returns:
        list[float]: 向量嵌入
    """
    model = _get_embedding_model()
    if model is None:
        return [0.0] * 512
    try:
        embedding = model.encode(text)
        return embedding.tolist()
    except Exception as e:
        print(f"[搜索] Embedding 生成失败: {e}")
        return [0.0] * 512
