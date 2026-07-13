"""统一上下文检索 — 合并四路记忆源

Working Memory   → chat_history（最近 N 条消息）
Session Memory   → session.key_facts（会话级事实，当前 session 生效）
User Memory      → user_memory.facts（用户级事实，跨 session 永久生效）
External KB      → hybrid_search（知识库检索）
"""

from __future__ import annotations

from dataclasses import dataclass, field

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.wiki_agent.agent.tools import search_tools
from app.wiki_agent.agent.tools.query_rewriter import rewrite_query
from app.wiki_agent.session import store as session_store
# 预算常量（字符数，约 1 token ≈ 2.5 中文字符）
MAX_HISTORY_CHARS = 800
MAX_WIKI_CHARS = 1200
MAX_SESSION_FACTS_CHARS = 400
MAX_USER_FACTS_CHARS = 600
HISTORY_RECENT_COUNT = 10


@dataclass
class RetrievedContext:
    """统一检索结果"""

    wiki_results: list[dict] = field(default_factory=list)
    user_facts: list[dict] = field(default_factory=list)      # 用户级持久事实 [{"content", "type", "confidence"}]
    session_facts: list[dict] = field(default_factory=list)    # 会话级事实 [{"content", "type", "confidence"}]
    history_summary: str = ""

    @property
    def has_content(self) -> bool:
        return bool(self.wiki_results or self.user_facts or self.session_facts or self.history_summary)

    # 向后兼容：key_facts 映射到 session_facts
    @property
    def key_facts(self) -> list[dict]:
        return self.session_facts

    @key_facts.setter
    def key_facts(self, value):
        self.session_facts = value


async def retrieve_context(
    user_message: str,
    chat_history: list[BaseMessage],
    session_id: str | None = None,
) -> RetrievedContext:
    """统一检索四路记忆，返回 RetrievedContext。"""
    import asyncio
    from app.wiki_agent.agent.tools.query_rewriter import QueryComplexity

    loop = asyncio.get_running_loop()

    # ① 复杂度分级 + Query 改写 Pipeline
    t0 = loop.time()
    rewritten_queries, complexity = await rewrite_query(user_message, chat_history)
    t1 = loop.time()
    print(f"[Timing] rewrite_query: {(t1-t0)*1000:.0f}ms (complexity: {complexity.value})")

    # TRIVIAL: 跳过 RAG
    if complexity == QueryComplexity.TRIVIAL:
        user_facts = await session_store.get_user_memory()
        session_facts = await session_store.get_session_key_facts(session_id) if session_id else []
        history_summary = _summarize_history(chat_history, HISTORY_RECENT_COUNT)
        return RetrievedContext(
            wiki_results=[],
            user_facts=user_facts,
            session_facts=session_facts,
            history_summary=history_summary,
        )

    # ② External KB — 根据复杂度决定搜索策略
    seen_paths: set[str] = set()
    wiki_results: list[dict] = []

    t2 = loop.time()

    # SIMPLE/MEDIUM: 单次搜索，不 rerank
    if complexity in (QueryComplexity.SIMPLE, QueryComplexity.MEDIUM):
        search_func = lambda q: search_tools.hybrid_search(q, limit=3, enable_rerank=False)
    else:
        search_func = lambda q: search_tools.hybrid_search(q, limit=3, enable_rerank=True)

    # 并行执行所有搜索
    search_tasks = [asyncio.to_thread(search_func, q) for q in rewritten_queries]
    search_results = await asyncio.gather(*search_tasks, return_exceptions=True)

    for results in search_results:
        if isinstance(results, Exception):
            continue
        for r in results:
            path = r.get("path", "")
            if path and path not in seen_paths:
                seen_paths.add(path)
                wiki_results.append(r)
    wiki_results = wiki_results[:5]  # 最终取 top 5
    t3 = loop.time()
    print(f"[Timing] hybrid_search: {(t3-t2)*1000:.0f}ms")

    # ②b 兜底：如果改写查询全部无结果，用原始查询再搜一次
    if not wiki_results and user_message:
        fallback_results = await asyncio.to_thread(search_tools.hybrid_search, user_message, limit=3, enable_rerank=False)
        for r in fallback_results:
            path = r.get("path", "")
            if path and path not in seen_paths:
                seen_paths.add(path)
                wiki_results.append(r)
        wiki_results = wiki_results[:5]
        if wiki_results:
            print(f"[Context] 改写查询无结果，原始查询兜底命中 {len(wiki_results)} 条")

    # ③ User Memory — 用户级持久事实（跨 session）
    t4 = loop.time()
    user_facts: list[dict] = []
    user_facts = await session_store.get_user_memory()

    # ④ Session Memory — 会话级事实（当前 session）
    session_facts: list[dict] = []
    if session_id:
        session_facts = await session_store.get_session_key_facts(session_id)
    t5 = loop.time()
    print(f"[Timing] memory_load: {(t5-t4)*1000:.0f}ms")

    # ⑤ Working Memory — 最近对话历史
    history_summary = _summarize_history(chat_history, HISTORY_RECENT_COUNT)

    return RetrievedContext(
        wiki_results=wiki_results,
        user_facts=user_facts,
        session_facts=session_facts,
        history_summary=history_summary,
    )


def build_context_block(ctx: RetrievedContext) -> str:
    """按优先级将 RetrievedContext 组装为文本块（带预算裁剪）。"""
    if not ctx.has_content:
        return ""

    blocks: list[str] = []
    budget = MAX_HISTORY_CHARS + MAX_WIKI_CHARS + MAX_SESSION_FACTS_CHARS + MAX_USER_FACTS_CHARS

    # ── 优先级 1: User Memory（用户级持久事实，最重要）──
    if ctx.user_facts:
        lines = [f"- {f['content']}" for f in ctx.user_facts[:10] if isinstance(f, dict)]
        user_text = "\n".join(lines)
        if len(user_text) > MAX_USER_FACTS_CHARS:
            user_text = user_text[:MAX_USER_FACTS_CHARS] + "..."
        blocks.append(f"[用户记忆]\n{user_text}")
        budget -= len(user_text)

    # ── 优先级 2: Session Memory（会话级事实）──
    if ctx.session_facts:
        lines = [f"- [{f.get('type', '')}] {f['content']}" for f in ctx.session_facts[:10] if isinstance(f, dict)]
        session_text = "\n".join(lines)
        if len(session_text) > MAX_SESSION_FACTS_CHARS:
            session_text = session_text[:MAX_SESSION_FACTS_CHARS] + "..."
        blocks.append(f"[会话记忆]\n{session_text}")
        budget -= len(session_text)

    # ── 优先级 3: wiki_results ──
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
            blocks.append("[知识库搜索结果]\n" + "\n".join(wiki_lines))
            budget -= used

    # ── 优先级 4: history_summary ──
    if ctx.history_summary:
        remaining = min(MAX_HISTORY_CHARS, budget - 100)
        if remaining > 50:
            hist = ctx.history_summary
            if len(hist) > remaining:
                hist = hist[:remaining] + "..."
            blocks.append(f"[对话历史]\n{hist}")

    return "\n\n".join(blocks)


def build_context_block_from_dict(data: dict) -> str:
    """从字典构建上下文块（用于复用已检索的上下文）。"""
    # 创建一个临时的 RetrievedContext 对象
    ctx = RetrievedContext()
    ctx.wiki_results = data.get("wiki_results", [])
    ctx.user_facts = data.get("user_facts", [])
    ctx.session_facts = data.get("key_facts", [])
    ctx.history_summary = data.get("history_summary", "")
    return build_context_block(ctx)


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
