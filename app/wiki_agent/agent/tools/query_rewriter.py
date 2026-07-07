"""Query 改写 Pipeline — 前置路由分类 + 上下文补齐 + 多策略改写 + 相似度校验

Pipeline:
    1. Contextualizer  — 多轮对话指代消解（检测到代词才触发）
    2. QueryClassifier — LLM 轻量分类 → 路由到不同改写策略
    3. QueryRewriter   — 按分类结果执行对应改写策略
    4. SimilarityValidator — 过滤掉与原始 query 语义偏离的改写
"""

from __future__ import annotations

import asyncio
import json as _json
import re
from enum import Enum

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_openai import ChatOpenAI

from app.wiki_agent.agent.llm_factory import create_chat_llm
from app.wiki_agent.agent.tools.embeddings import generate_embedding
from app.wiki_agent.config import settings


# ── 常量 ──────────────────────────────────────────────────────

# 中文常见代词/指示词，用于判断是否需要上下文补齐
_PRONOUN_PATTERN = re.compile(
    r"(它|它们|他|她|这个|那个|这些|那些|上面|之前|刚才|上述|前者|后者|哪个|什么)"
)

# ── Query 分类枚举 ────────────────────────────────────────────


class QueryType(str, Enum):
    """Query 路由分类"""

    DIRECT = "direct"  # 简单明确，直接传入不改写
    SIMPLE_FACTUAL = "simple"  # 简单事实查询，轻微改写
    COMPLEX = "complex"  # 复杂问题，需分解
    AMBIGUOUS = "ambiguous"  # 模糊/口语化，需 HyDE


# ── LLM 工厂 ─────────────────────────────────────────────────


def _get_rewrite_llm(temperature: float = 0, max_tokens: int = 200) -> ChatOpenAI:
    """获取用于 query 改写的轻量 LLM 实例"""
    return create_chat_llm(temperature=temperature, max_tokens=max_tokens)


# ── 1. 上下文补齐 ────────────────────────────────────────────


class Contextualizer:
    """多轮对话指代消解 — 检测到代词时，用 LLM 将 query 改写为自包含问题"""

    try:
        from prompts import get_prompt as _gp
        _PROMPT = _gp("wiki_agent/contextualize")
    except Exception:
        _PROMPT = """请将以下用户问题结合对话历史，改写为一个独立、完整的搜索查询。
要求：
- 消除所有代词（它、这个、那个等），替换为具体指代对象
- 保留原始问题的完整语义
- 只输出改写后的查询，不要解释

## 对话历史
{history}

## 用户问题
{query}

## 改写后的查询："""

    @staticmethod
    def needs_contextualize(query: str) -> bool:
        """规则检测：query 是否含代词"""
        return bool(_PRONOUN_PATTERN.search(query))

    @staticmethod
    async def contextualize(query: str, chat_history: list[BaseMessage]) -> str:
        """用 LLM 做指代消解，返回自包含的 query"""
        recent = chat_history[-6:]
        parts = []
        for msg in recent:
            role = "用户" if isinstance(msg, HumanMessage) else "助手"
            content = str(getattr(msg, "content", ""))[:200]
            parts.append(f"{role}: {content}")
        history_text = "\n".join(parts) or "无"

        prompt = Contextualizer._PROMPT.format(history=history_text, query=query)

        try:
            llm = _get_rewrite_llm(max_tokens=100)
            resp = await llm.ainvoke([HumanMessage(content=prompt)])
            result = resp.content.strip()
            # 防止 LLM 返回空或过长
            if result and len(result) < 200:
                return result
        except Exception as exc:
            print(f"[QueryRewrite] 上下文补齐失败: {exc}")

        return query


# ── 2. Query 路由分类器 ──────────────────────────────────────


class QueryClassifier:
    """用 LLM 做轻量 4 分类，路由到不同改写策略"""

    try:
        from prompts import get_prompt as _gp
        _PROMPT = _gp("wiki_agent/query_classify")
    except Exception:
        _PROMPT = """你是一个查询分类器。请将用户查询分类为以下四种类型之一：

- direct: 简单明确的事实查询，无需改写即可直接检索。例如："Python 的 GIL 是什么"
- simple: 简单但可以轻微改写以提高检索效果。例如："介绍一下向量数据库"
- complex: 复杂问题，需要拆解为多个子问题。例如："比较 Milvus 和 Pinecone 在性能和易用性上的差异"
- ambiguous: 模糊、口语化、省略主语的查询。例如："那个能存向量的东西叫啥" "怎么优化"

请只输出类型名称，不要解释。

用户查询：{query}

类型："""

    @staticmethod
    async def classify(query: str) -> QueryType:
        try:
            llm = _get_rewrite_llm(max_tokens=10)
            resp = await llm.ainvoke([HumanMessage(content=QueryClassifier._PROMPT.format(query=query))])
            raw = resp.content.strip().lower()

            if "complex" in raw:
                return QueryType.COMPLEX
            if "ambiguous" in raw:
                return QueryType.AMBIGUOUS
            if "simple" in raw:
                return QueryType.SIMPLE_FACTUAL
            if "direct" in raw:
                return QueryType.DIRECT
        except Exception as exc:
            print(f"[QueryRewrite] 分类失败: {exc}")

        # 失败时默认 direct，不改写
        return QueryType.DIRECT


# ── 3. 改写策略 ──────────────────────────────────────────────


class QueryRewriter:
    """按分类结果执行对应改写策略"""

    # ── Multi-Query ──
    try:
        from prompts import get_prompt as _gp
        _MULTI_QUERY_PROMPT = _gp("wiki_agent/multi_query")
    except Exception:
        _MULTI_QUERY_PROMPT = """请将以下查询改写为 3 个不同角度的搜索查询，以提高检索召回率。
要求：
- 每个改写保持原始语义，但从不同角度表述
- 改写 1：同义词替换
- 改写 2：更具体的描述
- 改写 3：更抽象/概括的描述
- 每行一个查询，不要编号

原始查询：{query}

改写查询："""

    # ── HyDE ──
    try:
        from prompts import get_prompt as _gp
        _HYDE_PROMPT = _gp("wiki_agent/hyde")
    except Exception:
        _HYDE_PROMPT = """请根据以下问题，生成一段假设性的知识库文档内容（约 100-150 字）。
这段文档应该像是知识库中真实存在的、能够回答该问题的文档片段。

问题：{query}

假设性文档："""

    # ── Decompose ──
    try:
        from prompts import get_prompt as _gp
        _DECOMPOSE_PROMPT = _gp("wiki_agent/decompose")
    except Exception:
        _DECOMPOSE_PROMPT = """请将以下复杂问题拆解为 2-3 个独立的子问题，每个子问题可以独立检索。
要求：
- 子问题之间互不依赖
- 合在一起能覆盖原始问题的全部信息需求
- 每行一个问题，不要编号

复杂问题：{query}

子问题："""

    @staticmethod
    async def direct(query: str) -> list[str]:
        """直传策略，返回原始 query"""
        return [query]

    @staticmethod
    async def multi_query(query: str) -> list[str]:
        """Multi-Query 策略：生成多个角度的改写"""
        try:
            llm = _get_rewrite_llm(max_tokens=200)
            resp = await llm.ainvoke([HumanMessage(content=QueryRewriter._MULTI_QUERY_PROMPT.format(query=query))])
            lines = [line.strip() for line in resp.content.strip().split("\n") if line.strip()]
            # 过滤空行和过长行
            valid = [line for line in lines if 2 < len(line) < 100]
            return [query] + valid[:3]  # 原始 query + 最多 3 个改写
        except Exception as exc:
            print(f"[QueryRewrite] Multi-Query 改写失败: {exc}")
            return [query]

    @staticmethod
    async def hyde(query: str) -> list[str]:
        """HyDE 策略：生成假设性文档作为检索 query"""
        try:
            llm = _get_rewrite_llm(max_tokens=300)
            resp = await llm.ainvoke([HumanMessage(content=QueryRewriter._HYDE_PROMPT.format(query=query))])
            hypothetical = resp.content.strip()
            if hypothetical and len(hypothetical) > 10:
                return [query, hypothetical]
        except Exception as exc:
            print(f"[QueryRewrite] HyDE 生成失败: {exc}")
        return [query]

    @staticmethod
    async def decompose(query: str) -> list[str]:
        """Decompose 策略：拆解为子问题"""
        try:
            llm = _get_rewrite_llm(max_tokens=200)
            resp = await llm.ainvoke([HumanMessage(content=QueryRewriter._DECOMPOSE_PROMPT.format(query=query))])
            lines = [line.strip() for line in resp.content.strip().split("\n") if line.strip()]
            valid = [line for line in lines if 2 < len(line) < 100]
            return [query] + valid[:3]
        except Exception as exc:
            print(f"[QueryRewrite] 分解失败: {exc}")
        return [query]


# ── 4. 相似度校验 ────────────────────────────────────────────


class SimilarityValidator:
    """校验改写后的 query 与原始 query 的语义一致性"""

    @staticmethod
    def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
        """计算两个向量的余弦相似度"""
        import math

        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def validate(
        original: str,
        rewritten_list: list[str],
        threshold: float = 0.7,
    ) -> list[str]:
        """过滤掉与原始 query 相似度低于阈值的改写

        Args:
            original: 原始 query
            rewritten_list: 改写后的 query 列表（含原始）
            threshold: 相似度阈值，低于此值的改写被丢弃

        Returns:
            过滤后的 query 列表，如果全部被过滤则返回 [original]
        """
        if not rewritten_list:
            return [original]

        original_vec = generate_embedding(original)
        validated = []

        for q in rewritten_list:
            if q == original:
                validated.append(q)
                continue
            q_vec = generate_embedding(q)
            sim = SimilarityValidator.cosine_similarity(original_vec, q_vec)
            if sim >= threshold:
                validated.append(q)
            else:
                print(f"[QueryRewrite] 过滤低相似度改写 (sim={sim:.3f}): {q}")

        return validated if validated else [original]


# ── 5. 复杂度分级 ─────────────────────────────────────────────

class QueryComplexity(Enum):
    """查询复杂度分级"""
    TRIVIAL = "trivial"    # 简单问候/闲聊，不需要 RAG
    SIMPLE = "simple"      # 简单查询，单次搜索，不改写
    MEDIUM = "medium"      # 中等查询，1-2 次改写，不 rerank
    COMPLEX = "complex"    # 复杂查询，完整 pipeline

# 不需要 RAG 的简单模式
_TRIVIAL_PATTERNS = [
    r'^(你好|hi|hello|hey|嗨|您好|早上好|下午好|晚上好)',
    r'^(你是谁|你叫什么|who are you|what are you)',
    r'^(谢谢|感谢|thanks|thank you)',
    r'^(再见|bye|拜拜|goodbye)',
    r'^(好的|ok|明白|了解|知道了)',
    r'^(嗯|哦|啊|哈)',
]

# 简单查询模式（只需要单次搜索）
_SIMPLE_PATTERNS = [
    r'^(什么是|怎么用|如何|解释|说明|介绍)',
    r'^(总结|概述|列举|列出|描述)',
    r'^(有哪些|有什么|包含什么|包括什么)',
    r'^(查询|搜索|查找|找)',
]


def classify_complexity(query: str) -> QueryComplexity:
    """基于规则快速判断查询复杂度（不调用 LLM）"""
    import re
    query = query.strip()

    # 检查 trivial 模式
    for pattern in _TRIVIAL_PATTERNS:
        if re.match(pattern, query, re.IGNORECASE):
            return QueryComplexity.TRIVIAL

    # 检查 simple 模式
    for pattern in _SIMPLE_PATTERNS:
        if re.match(pattern, query, re.IGNORECASE):
            return QueryComplexity.SIMPLE

    # 长度判断
    if len(query) < 10:
        return QueryComplexity.SIMPLE

    # 包含多个问号或复杂结构
    if query.count('?') > 1 or query.count('？') > 1:
        return QueryComplexity.COMPLEX

    # 默认 medium
    return QueryComplexity.MEDIUM


# ── 6. 合并分类+改写 ──────────────────────────────────────────

# 尝试从 YAML 加载 Prompt，失败则使用硬编码 fallback
try:
    from prompts import get_prompt
    _CLASSIFY_AND_REWRITE_PROMPT = get_prompt("wiki_agent/query_rewrite")
except Exception:
    _CLASSIFY_AND_REWRITE_PROMPT = """你是一个查询分析专家。请完成两个任务：

## 任务 1: 分类
将查询分为以下类型之一：
- direct: 简单直接查询，不需要改写
- simple: 简单事实性查询，需要多角度改写
- complex: 复杂查询，需要拆解为子问题
- ambiguous: 歧义查询，需要生成假设性文档

## 任务 2: 改写
根据分类结果生成改写查询：
- direct: 只返回原始查询
- simple: 生成 2-3 个不同角度的改写（同义词替换、更具体描述、更抽象概括）
- complex: 拆解为 2-3 个子问题
- ambiguous: 生成一段假设性知识库文档（100-150字）

## 输出格式
返回 JSON 对象：
{{
    "type": "分类结果",
    "rewrites": ["改写查询1", "改写查询2", ...]
}}

## 查询
{query}
"""


async def _classify_and_rewrite(query: str) -> tuple[list[str], QueryType]:
    """单次 LLM 调用同时完成分类和改写"""
    try:
        llm = _get_rewrite_llm(max_tokens=300)
        resp = await llm.ainvoke([
            HumanMessage(content=_CLASSIFY_AND_REWRITE_PROMPT.format(query=query))
        ])

        # 解析 JSON 响应
        content = resp.content.strip()
        # 尝试从 code fence 中提取 JSON
        import re
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
        json_text = json_match.group(1) if json_match else content

        data = _json.loads(json_text)
        query_type_str = data.get("type", "simple").lower()
        rewrites = data.get("rewrites", [])

        # 映射到 QueryType 枚举
        type_map = {
            "direct": QueryType.DIRECT,
            "simple": QueryType.SIMPLE_FACTUAL,
            "complex": QueryType.COMPLEX,
            "ambiguous": QueryType.AMBIGUOUS,
        }
        query_type = type_map.get(query_type_str, QueryType.SIMPLE_FACTUAL)

        # 过滤有效改写
        valid_rewrites = [q for q in rewrites if isinstance(q, str) and 2 < len(q) < 100]

        # 确保原始查询在结果中
        result = [query] + [q for q in valid_rewrites if q != query]

        return result[:4], query_type  # 最多返回 4 个查询

    except Exception as exc:
        print(f"[QueryRewrite] 合并分类改写失败: {exc}")
        return [query], QueryType.DIRECT


# ── 6. 主入口 ────────────────────────────────────────────────


async def rewrite_query(
    query: str,
    chat_history: list[BaseMessage],
    *,
    similarity_threshold: float | None = None,
    max_queries: int | None = None,
) -> tuple[list[str], QueryComplexity]:
    """完整 Query 改写 Pipeline（优化版：基于复杂度的分层策略）

    Pipeline:
        1. 复杂度分级（规则判断，不调用 LLM）
        2. 根据复杂度决定策略：
           - TRIVIAL: 跳过 RAG，直接返回空列表
           - SIMPLE: 单次搜索，不改写
           - MEDIUM: 1-2 次改写，不 rerank
           - COMPLEX: 完整 pipeline
        3. Contextualizer — 检测代词，有则做指代消解（仅 MEDIUM/COMPLEX）
        4. Classifier+Rewriter — 单次 LLM 调用同时完成分类和改写（仅 MEDIUM/COMPLEX）
        5. SimilarityValidator — 过滤低相似度改写

    Args:
        query: 用户原始查询
        chat_history: 对话历史
        similarity_threshold: 相似度阈值（默认从配置读取）
        max_queries: 最大返回 query 数（默认从配置读取）

    Returns:
        (queries, complexity) - 改写后的 query 列表和复杂度级别
    """
    # Step 1: 复杂度分级（规则判断，不调用 LLM）
    complexity = classify_complexity(query)
    print(f"[QueryRewrite] 复杂度: {complexity.value} (query: {query})")

    # TRIVIAL: 跳过 RAG
    if complexity == QueryComplexity.TRIVIAL:
        return [], complexity

    # SIMPLE: 单次搜索，不改写
    if complexity == QueryComplexity.SIMPLE:
        return [query], complexity

    # MEDIUM/COMPLEX: 完整 pipeline
    if not settings.QUERY_REWRITE_ENABLED:
        return [query], complexity

    threshold = similarity_threshold or settings.QUERY_REWRITE_SIMILARITY_THRESHOLD
    max_q = max_queries or settings.QUERY_REWRITE_MAX_QUERIES

    # MEDIUM: 限制改写数量
    if complexity == QueryComplexity.MEDIUM:
        max_q = min(max_q, 2)

    # Step 2: 上下文补齐（检测到代词才触发）
    working_query = query
    if chat_history and Contextualizer.needs_contextualize(query):
        working_query = await Contextualizer.contextualize(query, chat_history)
        if working_query != query:
            print(f"[QueryRewrite] 上下文补齐: {query} → {working_query}")

    # Step 3: 分类 + 改写（合并为单次 LLM 调用）
    rewritten, query_type = await _classify_and_rewrite(working_query)
    print(f"[QueryRewrite] 分类: {query_type.value} (query: {working_query})")

    # Step 4: 相似度校验
    validated = await asyncio.to_thread(SimilarityValidator.validate, working_query, rewritten, threshold)

    # 去重 + 限制数量
    seen = set()
    result = []
    for q in validated:
        if q not in seen:
            seen.add(q)
            result.append(q)
        if len(result) >= max_q:
            break

    print(f"[QueryRewrite] 最终 queries ({len(result)}): {result}")
    return result, complexity
