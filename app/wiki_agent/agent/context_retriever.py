"""统一上下文检索 — 合并三路记忆源

Short-term Memory  → chat_history（最近 N 条消息）
Long-term Memory   → session.key_facts（累积关键事实）
External KB (RAG)  → hybrid_search（知识库检索）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.wiki_agent.agent.tools import search_tools
from app.wiki_agent.session import store as session_store

# 预算常量（字符数，约 1 token ≈ 2.5 中文字符）
MAX_HISTORY_CHARS = 1000
MAX_WIKI_CHARS = 1500
MAX_FACTS_CHARS = 500
HISTORY_RECENT_COUNT = 10


@dataclass
class RetrievedContext:
    """统一检索结果"""
    wiki_results: list[dict] = field(default_factory=list)
    key_facts: list[str] = field(default_factory=list)
    history_summary: str = ""

    @property
    def has_content(self) -> bool:
        return bool(self.wiki_results or self.key_facts or self.history_summary)


async def retrieve_context(
    user_message: str,
    chat_history: list[BaseMessage],
    session_id: str | None = None,
) -> RetrievedContext:
    """统一检索三路记忆，返回 RetrievedContext。"""

    # ① External KB — hybrid search
    wiki_results = search_tools.hybrid_search(user_message, limit=3)

    # ② Long-term Memory — session key_facts
    key_facts: list[str] = []
    if session_id:
        key_facts = await session_store.get_session_key_facts(session_id)

    # ③ Short-term Memory — recent chat history
    history_summary = _summarize_history(chat_history, HISTORY_RECENT_COUNT)

    return RetrievedContext(
        wiki_results=wiki_results,
        key_facts=key_facts,
        history_summary=history_summary,
    )


def build_context_block(ctx: RetrievedContext) -> str:
    """按优先级将 RetrievedContext 组装为文本块（带预算裁剪）。"""
    if not ctx.has_content:
        return ""

    blocks: list[str] = []
    budget = MAX_HISTORY_CHARS + MAX_WIKI_CHARS + MAX_FACTS_CHARS  # ~3000

    # ── 优先级 1: key_facts（固定保留）──
    if ctx.key_facts:
        lines = [f"{i}. {f}" for i, f in enumerate(ctx.key_facts, 1)]
        facts_text = "\n".join(lines)
        if len(facts_text) > MAX_FACTS_CHARS:
            facts_text = facts_text[:MAX_FACTS_CHARS] + "..."
        blocks.append(f"[长期记忆]\n{facts_text}")
        budget -= len(facts_text)

    # ── 优先级 2: wiki_results ──
    if ctx.wiki_results:
        wiki_lines = []
        used = 0
        for r in ctx.wiki_results:
            line = f"- {r.get('title', '')} ({r.get('path', '')}): {r.get('snippet', '')}"
            if used + len(line) > min(MAX_WIKI_CHARS, budget - 200):
                break
            wiki_lines.append(line)
            used += len(line)
        if wiki_lines:
            blocks.append(f"[知识库搜索结果]\n" + "\n".join(wiki_lines))
            budget -= used

    # ── 优先级 3: history_summary ──
    if ctx.history_summary:
        remaining = min(MAX_HISTORY_CHARS, budget - 100)
        if remaining > 50:
            hist = ctx.history_summary
            if len(hist) > remaining:
                hist = hist[:remaining] + "..."
            blocks.append(f"[对话历史]\n{hist}")

    return "\n\n".join(blocks)


def _summarize_history(
    chat_history: list[BaseMessage],
    recent_count: int,
) -> str:
    """将最近 N 条消息拼接为摘要文本。"""
    if not chat_history:
        return ""

    recent = chat_history[-recent_count:]
    parts = []
    for msg in recent:
        if isinstance(msg, HumanMessage):
            role = "用户"
        elif isinstance(msg, AIMessage):
            role = "助手"
        else:
            continue
        content = str(getattr(msg, "content", ""))[:200]
        if content:
            parts.append(f"{role}: {content}")

    return "\n".join(parts)
