"""
Query Rewrite A/B Test — 对比开启/关闭 query rewrite 的检索命中率差异。

用法:
    python -m scripts.eval_query_rewrite_ab
"""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from typing import List

from scripts._fixtures import TEST_SET, hit_rate_at_k, mean_reciprocal_rank


async def run_with_rewrite(search_fn, test_set):
    """开启 query rewrite 的检索评估"""
    from app.wiki_agent.agent.tools.query_rewriter import rewrite_query

    hits1, hits3, mrr_sum, n = 0, 0, 0.0, 0
    details = []

    for query, expected in test_set:
        try:
            # 改写 query
            rewritten = await rewrite_query(query)
            # 用改写后的 query 检索（取第一个有效改写）
            search_query = rewritten[0] if rewritten else query
            raw = search_fn(search_query, limit=5)
            paths = [r["path"] for r in raw]
        except Exception:
            # 改写失败则回退原始 query
            try:
                raw = search_fn(query, limit=5)
                paths = [r["path"] for r in raw]
            except Exception:
                paths = []

        h1 = hit_rate_at_k(paths, expected, 1)
        h3 = hit_rate_at_k(paths, expected, 3)
        mrr = mean_reciprocal_rank(paths, expected)
        hits1 += 1 if h1 else 0
        hits3 += 1 if h3 else 0
        mrr_sum += mrr
        n += 1
        details.append((query, h1, paths[:3]))

    return hits1, hits3, mrr_sum, n, details


def run_without_rewrite(search_fn, test_set):
    """关闭 query rewrite 的检索评估（baseline）"""
    hits1, hits3, mrr_sum, n = 0, 0, 0.0, 0
    details = []

    for query, expected in test_set:
        try:
            raw = search_fn(query, limit=5)
            paths = [r["path"] for r in raw]
        except Exception:
            paths = []

        h1 = hit_rate_at_k(paths, expected, 1)
        h3 = hit_rate_at_k(paths, expected, 3)
        mrr = mean_reciprocal_rank(paths, expected)
        hits1 += 1 if h1 else 0
        hits3 += 1 if h3 else 0
        mrr_sum += mrr
        n += 1
        details.append((query, h1, paths[:3]))

    return hits1, hits3, mrr_sum, n, details


async def main():
    print("=" * 72)
    print("  Query Rewrite A/B Test — 20 条查询基准")
    print("=" * 72)
    print()

    from app.wiki_agent.agent.tools.search_tools import hybrid_search

    test_set = TEST_SET

    # ── Baseline: 无改写 ──
    print("  [A] Baseline (无 Query Rewrite)...")
    b_h1, b_h3, b_mrr, b_n, b_details = run_without_rewrite(hybrid_search, test_set)
    print(f"      Top-1={b_h1/b_n*100:.1f}%  Top-3={b_h3/b_n*100:.1f}%  MRR={b_mrr/b_n:.4f}")

    # ── Treatment: 有改写 ──
    print("  [B] Treatment (Query Rewrite ON)...")
    t_h1, t_h3, t_mrr, t_n, t_details = await run_with_rewrite(hybrid_search, test_set)
    print(f"      Top-1={t_h1/t_n*100:.1f}%  Top-3={t_h3/t_n*100:.1f}%  MRR={t_mrr/t_n:.4f}")

    # ── 对比 ──
    print()
    print("=" * 72)
    print("  对比结果")
    print("=" * 72)
    print(f"  {'指标':<12s} {'Baseline':>10s} {'+Rewrite':>10s} {'Delta':>10s}")
    print(f"  {'':-<44s}")

    for metric, bv, tv in [
        ("Top-1", b_h1/b_n*100, t_h1/t_n*100),
        ("Top-3", b_h3/b_n*100, t_h3/t_n*100),
        ("MRR", b_mrr/b_n, t_mrr/t_n),
    ]:
        delta = tv - bv
        sign = "+" if delta > 0 else ""
        print(f"  {metric:<12s} {bv:>9.1f}% {tv:>9.1f}% {sign}{delta:>8.1f}%")

    # ── 逐条对比 ──
    print()
    print("=" * 72)
    print("  逐条对比 (Top-1 Hit)")
    print("=" * 72)
    improved, degraded, same = 0, 0, 0
    for i, (query, expected) in enumerate(test_set):
        b_hit = b_details[i][1]
        t_hit = t_details[i][1]
        if t_hit and not b_hit:
            improved += 1
            print(f"  + IMPROVED: {query[:40]}")
        elif b_hit and not t_hit:
            degraded += 1
            print(f"  - DEGRADED: {query[:40]}")
        else:
            same += 1

    print()
    print(f"  Improved: {improved}  Degraded: {degraded}  Same: {same}")


if __name__ == "__main__":
    asyncio.run(main())
