"""Shared scoring helpers for dimension applicability and weighted overall scores."""

from __future__ import annotations

from typing import Any, Mapping, Optional


def is_applicable(dimension_result: Any) -> bool:
    """Return whether a dimension should participate in overall scoring."""
    if not isinstance(dimension_result, Mapping):
        return True
    return dimension_result.get("applicable", True) is not False


def dimension_score(dimension_result: Any) -> Optional[float]:
    """Extract a dimension score, returning None for non-applicable dimensions."""
    if not is_applicable(dimension_result):
        return None
    if isinstance(dimension_result, Mapping):
        score = dimension_result.get("overall")
        return float(score or 0)
    return None


def weighted_overall(
    dimension_results: Mapping[str, Any],
    weights: Mapping[str, float],
) -> float:
    """Compute weighted overall over applicable dimensions only.

    Non-applicable dimensions are excluded from both numerator and denominator.
    Remaining weights are normalized so the score stays on a 0-100 scale.
    """
    numerator = 0.0
    denominator = 0.0
    for dimension, weight in weights.items():
        result = dimension_results.get(dimension)
        if not is_applicable(result):
            continue
        numerator += float(weight) * float((result or {}).get("overall", 0) if isinstance(result, Mapping) else 0)
        denominator += float(weight)
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def score_values(
    dimension_results: Mapping[str, Any],
    weights: Mapping[str, float],
) -> dict[str, Optional[float]]:
    """Return per-dimension score values, using None for non-applicable dimensions."""
    return {dimension: dimension_score(dimension_results.get(dimension)) for dimension in weights}
