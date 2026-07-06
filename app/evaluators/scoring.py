"""各评估维度的适用性判断与加权总分计算工具函数。"""

from __future__ import annotations

from typing import Any, Mapping, Optional


def is_applicable(dimension_result: Any) -> bool:
    """判断某个评估维度是否应参与总分计算。

    非 Mapping 类型的结果（None、int、str 等）表示该维度未被评估或评估失败，
    因此不适用（返回 False）。
    """
    if not isinstance(dimension_result, Mapping):
        return False
    return dimension_result.get("applicable", True) is not False


def dimension_score(dimension_result: Any) -> Optional[float]:
    """提取某个评估维度的分数，不适用的维度返回 None。"""
    if not is_applicable(dimension_result):
        return None
    if isinstance(dimension_result, Mapping):
        score = dimension_result.get("overall")
        if score is None:
            return None
        return float(score)
    return None


def weighted_overall(
    dimension_results: Mapping[str, Any],
    weights: Mapping[str, float],
) -> float:
    """仅对适用的维度计算加权总分。

    不适用的维度会从分子和分母中同时剔除，
    剩余权重会被归一化，使最终分数保持在 0-100 区间。
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
    """返回各维度的分数值，不适用的维度对应值为 None。"""
    return {dimension: dimension_score(dimension_results.get(dimension)) for dimension in weights}
