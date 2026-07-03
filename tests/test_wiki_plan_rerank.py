"""Tests for Wiki Agent reranker model resolution."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from app.wiki_agent.agent.tools import reranker


def test_resolve_rerank_model_id_uses_hub_when_local_weights_missing(tmp_path: Path) -> None:
    local = tmp_path / "bge-reranker-base"
    local.mkdir()
    (local / "config.json").write_text("{}", encoding="utf-8")

    with patch.object(reranker.settings, "RERANK_MODEL_PATH", str(local)):
        with patch.object(reranker.settings, "RERANK_MODEL", "BAAI/bge-reranker-base"):
            assert reranker.resolve_rerank_model_id() == "BAAI/bge-reranker-base"


def test_resolve_rerank_model_id_uses_local_when_weights_present(tmp_path: Path) -> None:
    local = tmp_path / "bge-reranker-base"
    local.mkdir()
    (local / "model.safetensors").write_bytes(b"fake")

    with patch.object(reranker.settings, "RERANK_MODEL_PATH", str(local)):
        with patch.object(reranker, "_weight_is_valid", return_value=True):
            assert reranker.resolve_rerank_model_id() == str(local)


def test_get_reranker_status_reports_missing_weights(tmp_path: Path) -> None:
    local = tmp_path / "bge-reranker-base"
    local.mkdir()

    reranker._reranker_model = None
    reranker._reranker_load_error = "missing weights"

    with patch.object(reranker.settings, "RERANK_MODEL_PATH", str(local)):
        with patch.object(reranker.settings, "RERANK_ENABLED", True):
            status = reranker.get_reranker_status()

    assert status["enabled"] is True
    assert status["loaded"] is False
    assert status["has_local_weights"] is False
    assert status["error"] == "missing weights"
