"""Shared embedding model loader for Wiki Agent."""

from __future__ import annotations

from pathlib import Path

from app.wiki_agent.config import settings

_embedding_model = None


def get_embedding_model():
    """Load and cache the sentence-transformers embedding model."""
    global _embedding_model
    if _embedding_model is not None:
        return _embedding_model

    try:
        from sentence_transformers import SentenceTransformer

        local_path = Path(settings.EMBEDDING_MODEL_PATH)
        model_id = str(local_path) if local_path.exists() else settings.EMBEDDING_MODEL
        _embedding_model = SentenceTransformer(model_id)
        print(f"[Wiki Agent] Embedding model loaded: {model_id}")
    except Exception as exc:
        print(f"[Wiki Agent] Embedding model load failed: {exc}")
        _embedding_model = None
    return _embedding_model


def generate_embedding(text: str) -> list[float]:
    """Generate a vector embedding for text."""
    model = get_embedding_model()
    if model is None:
        return [0.0] * settings.EMBEDDING_DIM
    try:
        return model.encode(text).tolist()
    except Exception as exc:
        print(f"[Wiki Agent] Embedding generation failed: {exc}")
        return [0.0] * settings.EMBEDDING_DIM
