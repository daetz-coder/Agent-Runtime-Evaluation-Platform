"""
CI Gate — run golden suite + optional regression check, exit non-zero on failure.

Usage:
    python -m app.benchmarks.run_ci_gate
    python -m app.benchmarks.run_ci_gate --golden-only
    python -m app.benchmarks.run_ci_gate --regression-base <eval_id> --regression-head <eval_id>
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from app.benchmarks.golden.runner import GoldenSuiteRunner, print_results

logger = logging.getLogger(__name__)


async def run_golden(fail_fast: bool = False) -> bool:
    """Run golden suite. Returns True if all pass."""
    runner = GoldenSuiteRunner()
    results = await runner.run_all(fail_fast=fail_fast)
    print_results(results)
    return all(r.passed for r in results)


async def run_regression(base_eval_id: str, head_eval_id: str) -> bool:
    """Run regression check between two evaluations. Returns True if no regression."""
    from app.services.regression_detection import RegressionDetectionService

    service = RegressionDetectionService()
    report = await service.compare(
        base_eval_id=base_eval_id,
        head_eval_id=head_eval_id,
        include_diff=True,
    )

    print(f"\n{'=' * 60}")
    print(f"Regression Check: {report.base_evaluation_id} → {report.head_evaluation_id}")
    print(f"{'=' * 60}")
    print(f"  {report.summary}")
    print(f"  Overall change: {report.overall_change:+.1f}")
    for dim, dim_info in report.dimensions.items():
        arrow = "🔴" if dim_info.is_regression else "✅"
        print(f"  {arrow} {dim}: {dim_info.base_score:.0f} → {dim_info.head_score:.0f} ({dim_info.delta:+.1f})")
    print(f"\n  Conclusion: {'🔴 REGRESSION DETECTED' if report.has_regression else '✅ No regression'}")
    print(f"{'=' * 60}\n")

    return not report.has_regression


async def main_async() -> int:
    parser = argparse.ArgumentParser(description="CI Gate for Agent Evaluation Platform")
    parser.add_argument("--golden-only", action="store_true", help="Only run golden suite")
    parser.add_argument("--regression-base", type=str, default="", help="Base evaluation ID")
    parser.add_argument("--regression-head", type=str, default="", help="Head evaluation ID")
    parser.add_argument("--fail-fast", action="store_true", help="Stop golden suite at first failure")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    all_pass = True

    # Always run golden suite first
    print("\n--- Step 1: Golden Test Suite ---")
    golden_ok = await run_golden(fail_fast=args.fail_fast)
    if not golden_ok:
        all_pass = False
        if args.fail_fast:
            print("FAIL: Golden suite failed with --fail-fast")
            return 1

    # Regression check
    if args.regression_base and args.regression_head and not args.golden_only:
        print("\n--- Step 2: Regression Check ---")
        regression_ok = await run_regression(args.regression_base, args.regression_head)
        if not regression_ok:
            all_pass = False

    if all_pass:
        print("\n✅ CI Gate: ALL CHECKS PASSED")
        return 0
    else:
        print("\n❌ CI Gate: SOME CHECKS FAILED")
        return 1


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    sys.exit(main())
