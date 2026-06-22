"""
Wiki-Agent 检索评估脚本

对比 BM25 (keyword) / Semantic / Hybrid (RRF) 三种搜索策略的准确率。

用法:
    python -m tests.eval_retrieval

要求:
    - 先启动后端使索引初始化，或确保 chroma_db + BM25 索引已存在
"""

import sys
import os
from pathlib import Path

# 确保能从项目根目录导入 app 包
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from typing import List, Tuple


# ══════════════════════════════════════════════════════════
# 测试集：每个 (query, expected_doc_paths)
# 基于 example/wiki-agent/knowledge/ 的实际文档编写
# ══════════════════════════════════════════════════════════
TEST_SET: List[Tuple[str, List[str]]] = [
    # ── Wiki Agent 系统 ──
    (
        "Wiki Agent 有哪些核心功能",
        ["system/wiki-agent-助手介绍.md"],
    ),
    (
        "如何用 AI 管理个人知识库",
        ["welcome.md", "system/wiki-agent-助手介绍.md"],
    ),
    (
        "知识库内容有哪些分类",
        ["notes/知识库内容概述.md"],
    ),
    (
        "项目开发分哪几步",
        ["知识汇总.md"],
    ),

    # ── LangChain / Agent 技术 ──
    (
        "bind_tools 第一次发送什么给 LLM",
        ["notes/bind_tools-工作机制详解.md"],
    ),
    (
        "with_structured_output 和 PydanticOutputParser 的区别",
        ["notes/langchain-知识提取方法对比.md"],
    ),
    (
        "LangChain 结构化输出方法",
        ["notes/langchain-知识提取方法对比.md"],
    ),

    # ── Kubernetes ──
    (
        "Kubernetes 容器编排核心架构",
        ["development/tools/kubernetes-k8s-全面介绍.md", "notes/kubernetes-k8s.md"],
    ),
    (
        "K8S 的主要特点",
        ["notes/kubernetes-k8s.md", "development/tools/kubernetes-k8s-全面介绍.md"],
    ),

    # ── Ubuntu / Linux ──
    (
        "Ubuntu 20.04 和 18.04 版本区别",
        ["notes/ubuntu-2004与1804版本区别.md"],
    ),
    (
        "Ubuntu 系统介绍",
        ["notes/ubuntu系统全面介绍.md"],
    ),

    # ── Python ──
    (
        "Python 语言核心特点",
        ["programming/python-编程语言.md"],
    ),
    (
        "Python 变量定义和基本语法",
        ["programming/python/python-基础知识.md"],
    ),

    # ── 开发工具 ──
    (
        "CRUD 同步机制中如何集成 ChromaDB",
        ["development/knowledge-management/完整的crud同步机制架构.md"],
    ),
    (
        "Git 常用命令",
        ["development/tools/git-常用命令.md"],
    ),

    # ── 软件测试 ──
    (
        "黑盒测试的方法和特点",
        ["software/testing/黑盒测试.md"],
    ),
    (
        "什么是黑盒测试",
        ["software/testing/黑盒测试.md"],
    ),

    # ── 个人知识管理 ──
    (
        "个人 Wiki 知识库设计理念",
        ["welcome.md"],
    ),
    (
        "开发路线图：从基础功能到 AI 对话",
        ["知识汇总.md"],
    ),
]

assert len(TEST_SET) == 20, f"Expected 20 test cases, got {len(TEST_SET)}"


# ══════════════════════════════════════════════════════════
# 评估指标
# ══════════════════════════════════════════════════════════

def hit_rate_at_k(results_paths: List[str], expected: List[str], k: int) -> bool:
    """Top-K 中是否包含至少一个预期文档。"""
    top_k = results_paths[:k]
    return any(exp in top_k for exp in expected)


def mean_reciprocal_rank(results_paths: List[str], expected: List[str]) -> float:
    """MRR: 第一个相关文档的排名的倒数。"""
    for rank, path in enumerate(results_paths, 1):
        if path in expected:
            return 1.0 / rank
    return 0.0


# ══════════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════════

def main():
    print("=" * 72)
    print("  Wiki-Agent 检索评估 — 三种策略对比")
    print("=" * 72)

    # ── 导入搜索函数（延迟导入，避免影响测试集合加载） ──
    try:
        from app.wiki_agent.agent.tools.search_tools import (
            keyword_search,
            semantic_search,
            hybrid_search,
        )
    except ImportError as e:
        print(f"\n❌ 导入搜索模块失败: {e}")
        print("   请确认项目已安装 (pip install -e .) 且 .env 文件存在")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 搜索模块初始化失败: {e}")
        print("   这通常是因为 ChromaDB / BM25 索引未初始化")
        print("   请先启动 Wiki-Agent 后端以触发索引初始化")
        sys.exit(1)

    strategies = {
        "BM25 (keyword)": keyword_search,
        "Semantic (vector)": semantic_search,
        "Hybrid (RRF)": hybrid_search,
    }

    # ── 逐条评估 ──
    results: dict[str, dict] = {
        name: {"hits_1": 0, "hits_3": 0, "mrr": 0.0, "n": 0}
        for name in strategies
    }

    print()
    for i, (query, expected) in enumerate(TEST_SET, 1):
        print(f"  [{i:2d}/{len(TEST_SET)}] {query[:50]:50s}  →  {expected[0]}")

        for name, search_fn in strategies.items():
            try:
                raw = search_fn(query, limit=5)
                paths = [r["path"] for r in raw]
            except Exception as e:
                print(f"      ⚠ {name}: 搜索失败 — {e}")
                continue

            hit1 = hit_rate_at_k(paths, expected, 1)
            hit3 = hit_rate_at_k(paths, expected, 3)
            mrr = mean_reciprocal_rank(paths, expected)

            results[name]["hits_1"] += 1 if hit1 else 0
            results[name]["hits_3"] += 1 if hit3 else 0
            results[name]["mrr"] += mrr
            results[name]["n"] += 1

    # ── 汇总输出 ──
    print()
    print("=" * 72)
    print("  📊 汇总结果")
    print("=" * 72)
    print(f"  测试集: {len(TEST_SET)} 条查询")
    print()

    header = f"  {'策略':<24s} {'Top-1':>8s} {'Top-3':>8s} {'MRR':>8s} {'样本数':>6s}"
    print(header)
    print("  " + "-" * 56)

    best_1 = ("", 0)
    best_3 = ("", 0)
    best_mrr = ("", 0.0)

    for name, r in results.items():
        n = r["n"] or 1
        hit1_pct = r["hits_1"] / n * 100
        hit3_pct = r["hits_3"] / n * 100
        mrr_val = r["mrr"] / n

        print(f"  {name:<24s} {hit1_pct:>7.1f}% {hit3_pct:>7.1f}% {mrr_val:>7.4f} {r['n']:>6d}")

        if r["n"] > 0 and hit1_pct > best_1[1]:
            best_1 = (name, hit1_pct)
        if r["n"] > 0 and hit3_pct > best_3[1]:
            best_3 = (name, hit3_pct)
        if r["n"] > 0 and mrr_val > best_mrr[1]:
            best_mrr = (name, mrr_val)

    print()
    print(f"  🏆 Top-1 最佳: {best_1[0]} ({best_1[1]:.1f}%)")
    print(f"  🏆 Top-3 最佳: {best_3[0]} ({best_3[1]:.1f}%)")
    print(f"  🏆 MRR 最佳:  {best_mrr[0]} ({best_mrr[1]:.4f})")


if __name__ == "__main__":
    main()
