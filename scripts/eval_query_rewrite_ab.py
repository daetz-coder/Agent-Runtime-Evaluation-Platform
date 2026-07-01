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

from typing import List, Tuple

# 复用同一套测试集
TEST_SET: List[Tuple[str, List[str]]] = [
    ("Wiki Agent 有哪些核心功能", ["system/wiki-agent-助手介绍.md"]),
    ("如何用 AI 管理个人知识库", ["welcome.md", "system/wiki-agent-助手介绍.md"]),
    ("知识库内容有什么分类", ["notes/知识库内容概述.md"]),
    ("项目开发分几步", ["知识汇总.md"]),
    ("bind_tools 第一次发送什么给 LLM", ["notes/bind_tools-工作机制详解.md"]),
    ("with_structured_output 和 PydanticOutputParser 区别", ["notes/langchain-知识提取方法对比.md"]),
    ("LangChain 结构化输出方法", ["notes/langchain-知识提取方法对比.md"]),
    ("Kubernetes 容器编排核心架构", ["development/tools/kubernetes-k8s-全面介绍.md", "notes/kubernetes-k8s.md"]),
    ("K8S 的主要特点", ["notes/kubernetes-k8s.md", "development/tools/kubernetes-k8s-全面介绍.md"]),
    ("Ubuntu 20.04 和 18.04 版本区别", ["notes/ubuntu-2004与1804版本区别.md"]),
    ("Ubuntu 系统介绍", ["notes/ubuntu系统全面介绍.md"]),
    ("Python 语言核心特点", ["programming/python-编程语言.md"]),
    ("Python 变量定义和基本语法", ["programming/python/python-基础知识.md"]),
    ("CRUD 同步机制 ChromaDB", ["development/knowledge-management/完整的crud同步机制架构.md"]),
    ("Git 常用命令", ["development/tools/git-常用命令.md"]),
    ("黑盒测试的方法和特点", ["software/testing/黑盒测试.md"]),
    ("什么是黑盒测试", ["software/testing/黑盒测试.md"]),
    ("个人 Wiki 知识库设计理念", ["welcome.md"]),
    ("开发路线图", ["知识汇总.md"]),
    ("LangGraph bind_tools 工具调用机制", ["notes/bind_tools-工作机制详解.md"]),
]


def hit_rate_at_k(paths: List[str], expected: List[str], k: int) -> bool:
    return any(exp in paths[:k] for exp in expected)


def mean_reciprocal_rank(paths: List[str], expected: List[str]) -> float:
    for rank, p in enumerate(paths, 1):
        if p in expected:
            return 1.0 / rank
    return 0.0


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
