"""评估中间件 — Wiki Agent 与 SDK 的唯一桥接层。

wiki-agent 的业务代码（graph.py）不直接 import SDK，
所有评估相关的生命周期管理和事件记录都通过这个中间件完成。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.language_models import BaseChatModel

from app.wiki_agent.config import settings
from app.wiki_agent.session import store as session_store
from sdk import create_proxy_llm, get_collector, instrument_langgraph
from sdk.collector import ActionType

logger = logging.getLogger(__name__)

_plan_llm: BaseChatModel | None = None


# ── Graph / LLM 自动采集包裹 ────────────────────────────────


def instrument_graph(graph):
    """用 SDK 包裹 graph，自动采集节点执行/状态变化/工具调用/失败。"""
    return instrument_langgraph(graph)


def wrap_llm(llm: BaseChatModel) -> BaseChatModel:
    """用 SDK 包裹 LLM，自动采集 LLM 调用和工具决策。"""
    return create_proxy_llm(llm)


def _get_plan_llm() -> BaseChatModel:
    """Lazy LLM for structured plan generation (avoids circular import from graph.py)."""
    global _plan_llm
    if _plan_llm is not None:
        return _plan_llm

    from langchain_openai import ChatOpenAI

    model = settings.ZHIPUAI_CHAT_MODEL if settings.ZHIPUAI_API_KEY else settings.DEEPSEEK_MODEL
    api_key = settings.ZHIPUAI_API_KEY or settings.DEEPSEEK_API_KEY
    base_url = settings.ZHIPUAI_BASE_URL if settings.ZHIPUAI_API_KEY else settings.DEEPSEEK_BASE_URL
    if not api_key:
        raise ValueError("No LLM API key configured for plan generation")

    _plan_llm = wrap_llm(
        ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=0.3,
        )
    )
    return _plan_llm


def _parse_plan_json(content: str) -> dict | None:
    """Extract a JSON object from LLM output (supports markdown fences)."""
    text = content.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()

    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end <= start:
        return None

    try:
        return json.loads(text[start:end])
    except json.JSONDecodeError:
        return None


# ── 会话生命周期 ────────────────────────────────────────────


async def _generate_plan(goal: str) -> dict:
    """Use LLM to generate a structured plan from the user's goal.

    Returns a dict with 'plan' (text summary) and 'steps' (list of milestones).
    Fallback: returns {'goal': goal} on failure.
    """
    prompt = f"""你是一个项目管理专家。将以下用户目标分解为一个结构化的执行计划。

## 用户目标
{goal}

## 要求
返回一个 JSON 对象，包含：
1. "plan": 一句话总结整体方案
2. "steps": 关键步骤列表，每步包含 "step" (序号), "name" (步骤名), "description" (简要描述)
3. "estimated_complexity": "简单" / "中等" / "复杂"

## 输出格式
只返回 JSON，不要其他文字：
{{
    "plan": "整体方案一句话总结",
    "steps": [
        {{"step": 1, "name": "步骤名称", "description": "步骤描述"}},
        {{"step": 2, "name": "步骤名称", "description": "步骤描述"}}
    ],
    "estimated_complexity": "中等"
}}"""

    try:
        from langchain_core.prompts import ChatPromptTemplate

        p = ChatPromptTemplate.from_template("{prompt}")
        chain = p | _get_plan_llm()
        response = await chain.ainvoke({"prompt": prompt})

        parsed = _parse_plan_json(response.content)
        if parsed and parsed.get("steps"):
            return parsed
        if parsed:
            logger.warning("Plan JSON parsed but missing steps: %s", parsed)
        else:
            logger.warning("Failed to parse plan JSON from LLM response: %s", response.content[:300])
    except Exception as exc:
        logger.warning("Plan generation failed: %s", exc)

    return {"goal": goal}


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

    # Generate structured plan from goal before recording
    plan_data = await _generate_plan(goal)

    # Record plan with structured steps at top level so evaluator can find them
    plan_record = {"goal": goal, "context": context}
    if plan_data.get("plan"):
        plan_record["plan"] = plan_data["plan"]
    if plan_data.get("steps"):
        plan_record["steps"] = plan_data["steps"]
    if plan_data.get("estimated_complexity"):
        plan_record["estimated_complexity"] = plan_data["estimated_complexity"]

    if collector.use_inprocess():
        task_id = await collector.start_async(goal, context)
    else:
        task_id = collector.start(goal, context)

    # Record structured plan (LLM-generated decomposition of the goal)
    if plan_data.get("steps") and len(plan_data["steps"]) > 0:
        collector.record(
            ActionType.PLAN,
            {
                "goal": goal,
                "plan": plan_data.get("plan", goal),
                "steps": plan_data["steps"],
                "estimated_complexity": plan_data.get("estimated_complexity", ""),
            },
        )

    if session_id and task_id:
        await session_store.set_active_eval_task_id(session_id, task_id)

    return task_id


async def finish_session(auto_run: bool = True) -> str | None:
    """结束评估会话，flush 轨迹，可选触发评估。"""
    collector = get_collector()
    if collector.use_inprocess():
        return await collector.finish_async(auto_run=auto_run)
    return collector.finish(auto_run=auto_run)


# ── 语义事件记录（SDK 无法自动采集的部分）─────────────────


def record_retrieval(
    query: str,
    results: list[dict],
    duration_ms: float | None = None,
) -> None:
    """记录检索事件（hybrid_search 结果）。"""
    collector = get_collector()
    retrieved_docs = [
        {"title": r.get("title", ""), "path": r.get("path", ""), "snippet": r.get("snippet", "")} for r in results
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
