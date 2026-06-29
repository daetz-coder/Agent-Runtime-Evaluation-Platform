"""Cross-encoder reranker for Wiki Agent hybrid search."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from app.wiki_agent.config import settings

logger = logging.getLogger(__name__)

_reranker_model = None
_reranker_load_error: str | None = None

_WEIGHT_FILES = ("pytorch_model.bin", "model.safetensors")
_TEMP_DIR_NAMES = ("._____temp", ".____temp")
_MIN_PYTORCH_BYTES = 900_000_000
_MIN_SAFETENSORS_BYTES = 900_000_000


def _weight_is_valid(path: Path, name: str) -> bool:
    file_path = path / name
    if not file_path.exists():
        return False
    size = file_path.stat().st_size
    if name == "pytorch_model.bin":
        return size >= _MIN_PYTORCH_BYTES
    if name == "model.safetensors":
        return size >= _MIN_SAFETENSORS_BYTES
    return False


def _has_weights(path: Path) -> bool:
    return any(_weight_is_valid(path, name) for name in _WEIGHT_FILES)


def promote_temp_weights(local_path: Path) -> bool:
    """Promote ModelScope temp weight files to the model root if needed."""
    if _has_weights(local_path):
        return False

    promoted = False
    for temp_name in _TEMP_DIR_NAMES:
        temp_dir = local_path / temp_name
        if not temp_dir.is_dir():
            continue
        for name in _WEIGHT_FILES:
            src = temp_dir / name
            dst = local_path / name
            if src.exists() and not dst.exists() and _weight_is_valid(temp_dir, name):
                shutil.move(str(src), str(dst))
                logger.info("[Wiki Agent] Promoted reranker weight %s from %s", name, temp_name)
                promoted = True
            elif src.exists() and not _weight_is_valid(temp_dir, name):
                logger.warning(
                    "[Wiki Agent] Skipping incomplete reranker weight %s in %s (%d bytes)",
                    name,
                    temp_name,
                    src.stat().st_size,
                )
    return promoted


def resolve_rerank_model_id() -> str:
    """Use local path when PyTorch weights exist; otherwise HuggingFace hub id."""
    local_path = Path(settings.RERANK_MODEL_PATH) if settings.RERANK_MODEL_PATH else None
    if local_path and local_path.exists():
        promote_temp_weights(local_path)
        if _has_weights(local_path):
            return str(local_path)
        logger.warning(
            "Local reranker path %s has no PyTorch weights (%s); falling back to %s",
            local_path,
            ", ".join(_WEIGHT_FILES),
            settings.RERANK_MODEL,
        )
    return settings.RERANK_MODEL


def get_reranker_status() -> dict:
    """Lightweight reranker status for health checks (does not load the model)."""
    local_path = Path(settings.RERANK_MODEL_PATH) if settings.RERANK_MODEL_PATH else None
    has_local_weights = False
    if local_path and local_path.exists():
        promote_temp_weights(local_path)
        has_local_weights = _has_weights(local_path)

    return {
        "enabled": settings.RERANK_ENABLED,
        "loaded": _reranker_model is not None,
        "available": _reranker_model is not None or has_local_weights or bool(settings.RERANK_MODEL),
        "model_id": resolve_rerank_model_id(),
        "local_path": str(local_path) if local_path else None,
        "has_local_weights": has_local_weights,
        "error": _reranker_load_error,
    }


def get_reranker_model():
    """Load and cache the cross-encoder reranker model."""
    global _reranker_model, _reranker_load_error
    if _reranker_model is not None:
        return _reranker_model

    try:
        from sentence_transformers import CrossEncoder

        model_id = resolve_rerank_model_id()
        _reranker_model = CrossEncoder(model_id, max_length=settings.RERANK_MAX_LENGTH)
        _reranker_load_error = None
        logger.info("[Wiki Agent] Reranker model loaded: %s", model_id)
    except Exception as exc:
        _reranker_load_error = str(exc)
        logger.warning("[Wiki Agent] Reranker model load failed: %s", exc)
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
        logger.warning("[Wiki Agent] Rerank failed: %s", exc)
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
