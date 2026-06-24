"""搜索工具 — 语义搜索、BM25 搜索、RRF 混合搜索"""

from __future__ import annotations

from app.wiki_agent.agent.tools.embeddings import generate_embedding, get_embedding_model
from app.wiki_agent.agent.tools.vector_store import get_vector_store
from app.wiki_agent.config import settings

# 缓存 embedding 模型（兼容旧引用）
_embedding_model = None


def _get_embedding_model():
    """获取或加载 Embedding 模型（单例）"""
    return get_embedding_model()


def semantic_search(query: str, limit: int = 5) -> list[dict]:
    """语义搜索 — 基于 Milvus 向量相似度搜索

    Args:
        query: 搜索查询
        limit: 返回结果数量

    Returns:
        list[dict]: 搜索结果列表
    """
    try:
        store = get_vector_store()
        if not store.available:
            return keyword_search(query, limit)

        embedding = _generate_embedding(query)
        results = store.search(embedding, limit=limit * 3)

        seen_paths: dict[str, dict] = {}
        for hit in results:
            path = hit.get("path") or hit.get("chunk_id", "")
            score = hit.get("score", 0.0)
            if path not in seen_paths or score > seen_paths[path]["score"]:
                seen_paths[path] = {
                    "path": path,
                    "title": hit.get("title", ""),
                    "snippet": (hit.get("document") or "")[:200],
                    "score": score,
                    "search_type": "semantic",
                }

        formatted = sorted(seen_paths.values(), key=lambda x: x["score"], reverse=True)
        return formatted[:limit]
    except Exception as e:
        print(f"[搜索] 语义搜索失败: {e}")
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
    rrf_k = 60

    semantic_results = semantic_search(query, limit * 2)
    keyword_results = keyword_search(query, limit * 2)

    best_result: dict[str, dict] = {}
    for r in semantic_results:
        if r["path"] not in best_result:
            best_result[r["path"]] = r
    for r in keyword_results:
        if r["path"] not in best_result:
            best_result[r["path"]] = r

    rrf_scores: dict[str, float] = {}
    for rank, r in enumerate(semantic_results):
        rrf_scores.setdefault(r["path"], 0.0)
        rrf_scores[r["path"]] += 1.0 / (rrf_k + rank + 1)
    for rank, r in enumerate(keyword_results):
        rrf_scores.setdefault(r["path"], 0.0)
        rrf_scores[r["path"]] += 1.0 / (rrf_k + rank + 1)

    merged = []
    for path, rrf_score in rrf_scores.items():
        entry = {**best_result[path], "score": rrf_score, "search_type": "hybrid"}
        merged.append(entry)

    merged.sort(key=lambda x: x["score"], reverse=True)
    return merged[:limit]


def _generate_embedding(text: str) -> list[float]:
    """生成文本的向量嵌入"""
    return generate_embedding(text)
