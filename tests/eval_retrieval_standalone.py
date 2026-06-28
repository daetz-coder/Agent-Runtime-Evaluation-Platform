"""
Wiki-Agent 检索评估 — 独立版（不需要后端运行）

对比 BM25 / Semantic / Hybrid 三种搜索策略的准确率。
如果 ChromaDB 或 BM25 索引未初始化，会跳过对应策略。

用法:
    python -m tests.eval_retrieval_standalone
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from typing import List, Tuple

# ══════════════════════════════════════════════════════════
# 测试集
# ══════════════════════════════════════════════════════════

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


def main():
    print("=" * 72)
    print("  Wiki-Agent 检索评估 — 三种策略对比")
    print("=" * 72)
    print(f"  测试集: {len(TEST_SET)} 条查询")
    print()

    # ── 导入搜索函数 ──
    strategies = {}
    errors = {}

    try:
        from app.wiki_agent.agent.tools.search_tools import keyword_search

        strategies["BM25"] = keyword_search
    except Exception as e:
        errors["BM25"] = str(e)

    try:
        from app.wiki_agent.agent.tools.search_tools import semantic_search

        strategies["Semantic"] = semantic_search
    except Exception as e:
        errors["Semantic"] = str(e)

    try:
        from app.wiki_agent.agent.tools.search_tools import hybrid_search

        strategies["Hybrid"] = hybrid_search
    except Exception as e:
        errors["Hybrid"] = str(e)

    if not strategies:
        print("  ✗ 无法加载任何搜索策略！")
        for name, err in errors.items():
            print(f"    {name}: {err}")
        print()
        print("  请确保:")
        print("    1. pip install -e . 已执行")
        print("    2. .env 文件存在（含 DEEPSEEK_API_KEY）")
        print("    3. 先启动一次后端以初始化 ChromaDB + BM25 索引")
        return

    if errors:
        print("  ⚠ 部分策略加载失败:")
        for name, err in errors.items():
            print(f"    {name}: {err[:80]}...")
        print()

    print(f"  已加载策略: {', '.join(strategies.keys())}")
    print()

    # ── 逐条评估 ──
    results: dict = {name: {"hits_1": 0, "hits_3": 0, "mrr_sum": 0.0, "n": 0} for name in strategies}

    for i, (query, expected) in enumerate(TEST_SET, 1):
        for name, search_fn in strategies.items():
            try:
                raw = search_fn(query, limit=5)
                paths = [r["path"] for r in raw]
            except Exception:
                continue

            hit1 = hit_rate_at_k(paths, expected, 1)
            hit3 = hit_rate_at_k(paths, expected, 3)
            mrr = mean_reciprocal_rank(paths, expected)

            results[name]["hits_1"] += 1 if hit1 else 0
            results[name]["hits_3"] += 1 if hit3 else 0
            results[name]["mrr_sum"] += mrr
            results[name]["n"] += 1

    # ── 汇总 ──
    print("=" * 72)
    print("  检索准确率对比")
    print("=" * 72)
    print(f"  {'策略':<16s} {'Top-1':>8s} {'Top-3':>8s} {'MRR':>8s}")
    print(f"  {'':-<44s}")

    for name, r in results.items():
        n = r["n"] or 1
        h1 = r["hits_1"] / n * 100
        h3 = r["hits_3"] / n * 100
        m = r["mrr_sum"] / n
        print(f"  {name:<16s} {h1:>7.1f}% {h3:>7.1f}% {m:>7.4f}")

    # ── 优势分析 ──
    if len(strategies) >= 2:
        names = list(strategies.keys())
        print()
        print("=" * 72)
        print("  策略优势分析")
        print("=" * 72)
        for name in names:
            r = results[name]
            n = r["n"] or 1
            h1 = r["hits_1"] / n * 100
            mrr = r["mrr_sum"] / n
            # BM25 优势：中文关键词精确匹配
            # Semantic 优势：语义理解，同义词/近义词
            # Hybrid 优势：RRF 融合互补
            print(f"  {name}: Top-1={h1:.1f}%  MRR={mrr:.4f}")


if __name__ == "__main__":
    main()
