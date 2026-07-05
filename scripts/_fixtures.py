"""脚本共享的测试数据和辅助函数。

避免在多个评估脚本中重复定义相同的测试集和指标函数。
"""

from typing import List, Tuple

# ── 检索评估测试集 ──────────────────────────────────────

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


# ── 检索指标 ────────────────────────────────────────────


def hit_rate_at_k(paths: List[str], expected: List[str], k: int) -> bool:
    """前 k 个结果中是否命中至少一个预期路径。"""
    return any(exp in paths[:k] for exp in expected)


def mean_reciprocal_rank(paths: List[str], expected: List[str]) -> float:
    """平均倒数排名（MRR）。"""
    for rank, p in enumerate(paths, 1):
        if p in expected:
            return 1.0 / rank
    return 0.0
