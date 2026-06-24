"""Tests for RRF merge and cross-encoder rerank in hybrid search."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.wiki_agent.agent.tools import reranker, search_tools


def test_rrf_merge_orders_by_fused_score() -> None:
    """RRF should boost documents appearing in both semantic and BM25 lists."""
    semantic = [
        {"path": "a.md", "title": "A", "snippet": "alpha", "score": 0.9, "search_type": "semantic"},
        {"path": "b.md", "title": "B", "snippet": "beta", "score": 0.8, "search_type": "semantic"},
    ]
    keyword = [
        {"path": "b.md", "title": "B", "snippet": "beta", "score": 12.0, "search_type": "bm25"},
        {"path": "c.md", "title": "C", "snippet": "gamma", "score": 10.0, "search_type": "bm25"},
    ]

    merged = search_tools._rrf_merge(semantic, keyword)

    assert [item["path"] for item in merged] == ["b.md", "a.md", "c.md"]
    assert merged[0]["search_type"] == "hybrid"
    assert merged[0]["score"] > merged[1]["score"]


def test_rerank_results_updates_scores_and_type() -> None:
    """Reranker should replace score and preserve rrf_score."""
    candidates = [
        {"path": "a.md", "title": "A", "snippet": "alpha", "score": 0.01, "search_type": "hybrid"},
        {"path": "b.md", "title": "B", "snippet": "beta", "score": 0.02, "search_type": "hybrid"},
    ]
    mock_model = MagicMock()
    mock_model.predict.return_value = [0.2, 0.9]

    with patch.object(reranker, "get_reranker_model", return_value=mock_model):
        results = reranker.rerank_results("query", candidates, top_k=2)

    assert [item["path"] for item in results] == ["b.md", "a.md"]
    assert results[0]["search_type"] == "hybrid_rerank"
    assert results[0]["rrf_score"] == 0.02
    assert results[0]["score"] == 0.9
    mock_model.predict.assert_called_once()


def test_hybrid_search_applies_rerank_after_rrf() -> None:
    """hybrid_search pipeline should call rerank on RRF output."""
    semantic = [{"path": "a.md", "title": "A", "snippet": "alpha", "content": "alpha", "score": 0.9, "search_type": "semantic"}]
    keyword = [{"path": "b.md", "title": "B", "snippet": "beta", "content": "beta", "score": 12.0, "search_type": "bm25"}]
    reranked = [{"path": "b.md", "title": "B", "snippet": "beta", "score": 0.95, "search_type": "hybrid_rerank"}]

    with (
        patch.object(search_tools, "semantic_search", return_value=semantic),
        patch.object(search_tools, "keyword_search", return_value=keyword),
        patch.object(search_tools, "rerank_results", return_value=reranked) as mock_rerank,
    ):
        results = search_tools.hybrid_search("test query", limit=1)

    assert results == reranked
    mock_rerank.assert_called_once()
    merged_arg = mock_rerank.call_args[0][1]
    assert {item["path"] for item in merged_arg} == {"a.md", "b.md"}


def test_rerank_disabled_returns_rrf_order() -> None:
    """When RERANK_ENABLED=false, rerank_results should truncate without scoring."""
    candidates = [
        {"path": "a.md", "title": "A", "snippet": "alpha", "score": 0.02, "search_type": "hybrid"},
        {"path": "b.md", "title": "B", "snippet": "beta", "score": 0.01, "search_type": "hybrid"},
    ]

    with patch.object(reranker.settings, "RERANK_ENABLED", False):
        results = reranker.rerank_results("query", candidates, top_k=1)

    assert len(results) == 1
    assert results[0]["path"] == "a.md"
    assert results[0]["search_type"] == "hybrid"
