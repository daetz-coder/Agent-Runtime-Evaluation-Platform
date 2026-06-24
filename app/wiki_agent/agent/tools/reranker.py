"""Cross-encoder reranker for Wiki Agent hybrid search."""

from __future__ import annotations

from pathlib import Path

from app.wiki_agent.config import settings

_reranker_model = None


def get_reranker_model():
    """Load and cache the cross-encoder reranker model."""
    global _reranker_model
    if _reranker_model is not None:
        return _reranker_model

    try:
        from sentence_transformers import CrossEncoder

        local_path = Path(settings.RERANK_MODEL_PATH) if settings.RERANK_MODEL_PATH else None
        model_id = str(local_path) if local_path and local_path.exists() else settings.RERANK_MODEL
        _reranker_model = CrossEncoder(model_id, max_length=settings.RERANK_MAX_LENGTH)
        print(f"[Wiki Agent] Reranker model loaded: {model_id}")
    except Exception as exc:
        print(f"[Wiki Agent] Reranker model load failed: {exc}")
        _reranker_model = None
    return _reranker_model


def document_text(item: dict) -> str:
    """Build passage text for cross-encoder scoring."""
    title = str(item.get("title") or "").strip()
    content = str(item.get("content") or item.get("snippet") or "").strip()
    if title and content:
        return f"{title}\n{content}"
    return title or content


def rerank_results(query: str, candidates: list[dict], top_k: int) -> list[dict]:
    """Rerank RRF candidates with a cross-encoder; fallback to RRF order on failure."""
    if not candidates:
        return []

    if not settings.RERANK_ENABLED:
        return candidates[:top_k]

    model = get_reranker_model()
    if model is None:
        return candidates[:top_k]

    pairs = [(query, document_text(item)) for item in candidates]
    try:
        scores = model.predict(pairs)
    except Exception as exc:
        print(f"[Wiki Agent] Rerank failed: {exc}")
        return candidates[:top_k]

    reranked: list[dict] = []
    for item, score in zip(candidates, scores):
        entry = {**item}
        entry["rrf_score"] = float(entry.get("score", 0.0))
        entry["score"] = float(score)
        entry["search_type"] = "hybrid_rerank"
        reranked.append(entry)

    reranked.sort(key=lambda x: x["score"], reverse=True)
    return reranked[:top_k]
