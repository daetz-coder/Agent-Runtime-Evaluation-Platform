"""Unit tests for EvaluationService helpers."""

from app.services.evaluation_service import EvaluationService


def test_build_overall_from_parallel_normalizes_result() -> None:
    """Parallel eval output should map to OverallEvaluation fields."""
    service = EvaluationService(db=None)  # type: ignore[arg-type]
    parallel_result = {
        "planning": {
            "overall": 80,
            "feedback": "ok",
            "coverage": 80,
            "ordering": 80,
            "granularity": 80,
            "completeness": 80,
        },
        "tactical": {"overall": 70, "feedback": "ok", "relevance": 70, "efficiency": 70, "correctness": 70},
        "tool_use": {
            "overall": 75,
            "feedback": "ok",
            "selection_quality": 75,
            "parameter_accuracy": 75,
            "result_utilization": 75,
        },
        "memory": {"overall": 65, "feedback": "ok", "retention": 65, "relevance": 65, "consistency": 65},
        "replan": {
            "overall": 60,
            "feedback": "ok",
            "trigger_appropriateness": 60,
            "adaptation_quality": 60,
            "learning_from_failure": 60,
        },
        "retrieval": {
            "overall": 55,
            "feedback": "weak grounding",
            "relevance": 55,
            "evidence_accuracy": 50,
            "coverage": 60,
            "hallucination_detected": True,
            "missing_info": ["source doc"],
        },
        "overall": {"overall_score": 68.5},
    }

    overall = service._build_overall_from_parallel(parallel_result)

    assert overall.overall_score == 68.5
    assert overall.planning.overall == 80
    assert overall.retrieval is not None
    assert overall.retrieval.hallucination_detected is True
    assert "retrieval" in overall.summary.lower() or "检索" in overall.summary or "overall" in overall.summary.lower() or "得分" in overall.summary
    assert any("RAG" in rec or "retrieval" in rec.lower() or "检索" in rec for rec in overall.recommendations)


def test_build_recommendations_includes_retrieval() -> None:
    """Low retrieval score should produce a recommendation."""
    service = EvaluationService(db=None)  # type: ignore[arg-type]
    feedback = {
        "planning": {"overall": 90},
        "tactical": {"overall": 90},
        "tool_use": {"overall": 90},
        "memory": {"overall": 90},
        "replan": {"overall": 90},
        "retrieval": {"overall": 40},
    }
    recs = service._build_recommendations(feedback)
    assert any("RAG" in r or "retrieval" in r.lower() or "检索" in r or "RAG" in r.upper() for r in recs)


def test_build_overall_reweights_non_applicable_dimensions() -> None:
    """Non-applicable dimensions should be excluded from the weighted denominator."""
    service = EvaluationService(db=None)  # type: ignore[arg-type]
    parallel_result = {
        "planning": {
            "overall": 80,
            "feedback": "ok",
            "coverage": 80,
            "ordering": 80,
            "granularity": 80,
            "completeness": 80,
        },
        "tactical": {"overall": 80, "feedback": "ok", "relevance": 80, "efficiency": 80, "correctness": 80},
        "tool_use": {
            "applicable": False,
            "not_applicable_reason": "No tool calls were present in the trajectory.",
            "overall": 0,
            "feedback": "Not applicable",
            "selection_quality": 0,
            "parameter_accuracy": 0,
            "result_utilization": 0,
        },
        "memory": {"overall": 80, "feedback": "ok", "retention": 80, "relevance": 80, "consistency": 80},
        "replan": {
            "applicable": False,
            "not_applicable_reason": "No replanning was needed.",
            "overall": 0,
            "feedback": "Not applicable",
            "trigger_appropriateness": 0,
            "adaptation_quality": 0,
            "learning_from_failure": 0,
        },
        "retrieval": {"overall": 80, "feedback": "ok", "relevance": 80, "evidence_accuracy": 80, "coverage": 80},
    }

    overall = service._build_overall_from_parallel(parallel_result)

    assert overall.overall_score == 80
    assert overall.tool_use.applicable is False
    assert overall.replan.applicable is False
