"""
Golden Test Suite — curated trajectories with expected score ranges.

Each GoldenCase contains a known-good trajectory and the score range
each evaluator should produce.  Used for regression detection:
when an evaluator's judge prompt changes, the golden suite validates
that scores remain within the expected range.

To extend: add a new GoldenCase tuple with a realistic trajectory
and empirically-determined expected score ranges.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple


@dataclass
class GoldenCase:
    """A curated test trajectory with expected score ranges."""

    id: str
    description: str
    goal: str
    trajectory: List[Dict[str, Any]]
    expected_ranges: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    """Mapping: dimension_name → (min_score, max_score).  E.g. {"planning": (70, 95)}."""

    context: Dict[str, Any] = field(default_factory=dict)


from app.benchmarks.golden.case_excellent import GOLDEN_EXCELLENT
from app.benchmarks.golden.case_replan import GOLDEN_REPLAN
from app.benchmarks.golden.case_retrieval import GOLDEN_RETRIEVAL
from app.benchmarks.golden.case_tool_misuse import GOLDEN_TOOL_MISUSE

# List of all golden cases.  Each is manually crafted to exercise specific
# agent behaviors — excellent planning, tool misuse, replanning, etc.
GOLDEN_SUITE: List[GoldenCase] = [
    GOLDEN_EXCELLENT,
    GOLDEN_REPLAN,
    GOLDEN_RETRIEVAL,
    GOLDEN_TOOL_MISUSE,
]
