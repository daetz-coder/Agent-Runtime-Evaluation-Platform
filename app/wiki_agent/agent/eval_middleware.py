"""评估中间件 — Wiki Agent 与 SDK 的唯一桥接层。

wiki-agent 的业务代码（graph.py）不直接 import SDK，
所有评估相关的生命周期管理和事件记录都通过这个中间件完成。
"""

from __future__ import annotations

import logging
from typing import Any

from sdk import create_proxy_llm, get_collector, instrument_langgraph
from langchain_core.language_models import BaseChatModel

from app.wiki_agent.session import store as session_store

logger = logging.getLogger(__name__)


# ── Graph / LLM 自动采集包裹 ────────────────────────────────


def instrument_graph(graph):
    """用 SDK 包裹 graph，自动采集节点执行/状态变化/工具调用/失败。"""
    return instrument_langgraph(graph)


def wrap_llm(llm: BaseChatModel) -> BaseChatModel:
    """用 SDK 包裹 LLM，自动采集 LLM 调用和工具决策。"""
    return create_proxy_llm(llm)


# ── 会话生命周期 ────────────────────────────────────────────


async def start_session(
    goal: str,
    session_id: str | None = None,
    mode: str = "stream",
    **extra_context: Any,
) -> str:
    """启动评估会话，创建 task，返回 task_id。"""
    collector = get_collector()

    context = {
        "agent": "example/wiki-agent",
        "mode": mode,
        "session_id": session_id,
        **extra_context,
    }

    task_id = collector.start(goal, context)

    if session_id and task_id:
        await session_store.set_active_eval_task_id(session_id, task_id)

    return task_id


def finish_session(auto_run: bool = True) -> str | None:
    """结束评估会话，flush 轨迹，可选触发评估。"""
    return get_collector().finish(auto_run=auto_run)


# ── 语义事件记录（SDK 无法自动采集的部分）─────────────────


def record_retrieval(
    query: str,
    results: list[dict],
    duration_ms: float | None = None,
) -> None:
    """记录检索事件（hybrid_search 结果）。"""
    collector = get_collector()
    retrieved_docs = [
        {"title": r.get("title", ""), "path": r.get("path", ""), "snippet": r.get("snippet", "")}
        for r in results
    ]
    collector.record_retrieval(
        query=query,
        retrieved_docs=retrieved_docs,
        source="hybrid_search",
        top_k=len(results),
        duration_ms=duration_ms,
    )


def record_key_facts(facts: list[str]) -> None:
    """将 key_facts 记录为 memory_write 事件。"""
    collector = get_collector()
    for fact in facts:
        collector.record_memory_write(
            key=fact,
            value=fact,
            source="llm_extraction",
            memory_type="fact",
        )


def update_context(context_dict: dict[str, Any]) -> None:
    """更新评估上下文（通过 record 语义事件实现）。"""
    key_facts = context_dict.get("key_facts", [])
    if key_facts:
        record_key_facts(key_facts)
