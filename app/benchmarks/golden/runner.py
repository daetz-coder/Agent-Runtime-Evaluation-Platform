"""
GoldenSuiteRunner — run all golden cases and report pass/fail.

Used by:
  - ``make golden``        — run and show results
  - ``make check-ci``      — run + fail fast on regression
  - ``tests/test_golden_suite.py`` — CI test gate
"""

from __future__ import annotations

import asyncio
import logging
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.benchmarks.golden import GOLDEN_SUITE, GoldenCase
from app.graphs.evaluation_graph import evaluate_parallel
from app.models.schemas import TrajectoryStep

logger = logging.getLogger(__name__)


@dataclass
class GoldenResult:
    """Result of running a single golden case."""

    case_id: str
    description: str
    passed: bool
    scores: Dict[str, float] = field(default_factory=dict)
    failures: List[str] = field(default_factory=list)
    duration_ms: float = 0.0


class GoldenSuiteRunner:
    """Run all golden cases and validate scores against expected ranges."""

    async def run_all(
        self,
        fail_fast: bool = False,
        case_ids: Optional[List[str]] = None,
    ) -> List[GoldenResult]:
        """
        Run all (or specified) golden cases.

        Args:
            fail_fast: If True, stop at first failure.
            case_ids: Optional list of case IDs to run (run all if None).

        Returns:
            List of GoldenResult, one per case.
        """
        cases = [c for c in GOLDEN_SUITE if case_ids is None or c.id in case_ids]
        results: List[GoldenResult] = []

        for case in cases:
            result = await self._run_single(case)
            results.append(result)

            if not result.passed and fail_fast:
                logger.error("Golden case %s FAILED — stopping early", case.id)
                break

        return results

    async def _run_single(self, case: GoldenCase) -> GoldenResult:
        """Run evaluation on a single golden case."""
        import time

        from app.models.schemas import TrajectoryStep as TS

        steps = [
            TS(
                step_number=s["step_number"],
                action_type=s["action_type"],
                action_detail=s.get("action_detail", {}),
                observation=s.get("observation"),
            )
            for s in case.trajectory
        ]

        start = time.monotonic()
        try:
            scores_dict = await evaluate_parallel(case.goal, steps, case.context)
            duration_ms = (time.monotonic() - start) * 1000
        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000
            return GoldenResult(
                case_id=case.id,
                description=case.description,
                passed=False,
                failures=[f"Evaluation error: {e}"],
                duration_ms=duration_ms,
            )

        # Extract dimension scores
        scored: Dict[str, float] = {}
        failures: List[str] = []
        for dim, expected_range in case.expected_ranges.items():
            if dim == "overall":
                dim_data = scores_dict.get("overall", {})
                if isinstance(dim_data, dict):
                    score = float(dim_data.get("overall_score", 0))
                else:
                    score = 0.0
            else:
                dim_data = scores_dict.get(dim, {})
                score = float(dim_data.get("overall", 0)) if isinstance(dim_data, dict) else 0.0

            scored[dim] = score
            min_s, max_s = expected_range
            if score < min_s or score > max_s:
                failures.append(f"{dim}: got {score:.1f}, expected [{min_s:.0f}, {max_s:.0f}]")

        passed = len(failures) == 0
        if passed:
            logger.info("✅ %s — all %d dimensions passed", case.id, len(scored))
        else:
            logger.warning("❌ %s — %d failures:\n  %s", case.id, len(failures), "\n  ".join(failures))

        return GoldenResult(
            case_id=case.id,
            description=case.description,
            passed=passed,
            scores=scored,
            failures=failures,
            duration_ms=duration_ms,
        )


def print_results(results: List[GoldenResult]) -> None:
    """Print golden suite results to stdout in a readable format."""
    passed_count = sum(1 for r in results if r.passed)
    total = len(results)

    print(f"\n{'=' * 60}")
    print(f"Golden Test Suite Results: {passed_count}/{total} passed")
    print(f"{'=' * 60}")

    for r in results:
        status = "✅ PASS" if r.passed else "❌ FAIL"
        print(f"\n  {status} | {r.case_id}: {r.description}")
        print(f"       Duration: {r.duration_ms:.0f}ms")
        if r.scores:
            scores_str = " | ".join(f"{k}={v:.1f}" for k, v in sorted(r.scores.items()))
            print(f"       Scores:   {scores_str}")
        if r.failures:
            for f in r.failures:
                print(f"       ⚠  {f}")

    print(f"\n{'=' * 60}")
    overall = "ALL PASSED" if passed_count == total else f"{total - passed_count} FAILED"
    print(f"  {overall}")
    print(f"{'=' * 60}\n")


def main() -> int:
    """CLI entry point: python -m app.benchmarks.golden.runner"""
    import argparse

    parser = argparse.ArgumentParser(description="Run Golden Test Suite")
    parser.add_argument("--case", nargs="*", help="Run specific case IDs only")
    parser.add_argument("--fail-fast", action="store_true", help="Stop at first failure")
    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    runner = GoldenSuiteRunner()
    results = asyncio.run(
        runner.run_all(
            fail_fast=args.fail_fast,
            case_ids=args.case,
        )
    )
    print_results(results)

    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
