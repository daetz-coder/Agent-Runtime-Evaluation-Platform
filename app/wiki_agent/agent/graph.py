"""Wiki Agent — LangGraph 编排（search → respond → decide → execute）

纯业务逻辑。通过 SDK TrajectoryCollector 直接采集评估轨迹。
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import uuid
from collections.abc import AsyncGenerator
from typing import Any, Literal, TypedDict

import aiosqlite
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field

from app.wiki_agent.agent import knowledge_agent
from app.wiki_agent.agent.context_retriever import RetrievedContext, build_context_block, build_context_block_from_dict, retrieve_context
from app.wiki_agent.agent.llm_factory import create_chat_llm
from app.wiki_agent.agent.tools import crud_tools
from app.wiki_agent.config import settings
from sdk.collector import ActionType, get_collector
from app.wiki_agent.session import store as session_store

logger = logging.getLogger(__name__)

_CHECKPOINT_DB = os.path.join(os.path.dirname(settings.DB_PATH), "checkpoints.db")
os.makedirs(os.path.dirname(_CHECKPOINT_DB), exist_ok=True)

# 尝试从 YAML 加载 Prompt，失败则使用硬编码 fallback
try:
    from prompts import get_prompt
    SYSTEM_PROMPT = get_prompt("wiki_agent/system_prompt")
except Exception:
    SYSTEM_PROMPT = """你是一个智能知识助手。请用中文回答。

## 你的能力
1. 用你的知识详细回答用户的各种问题
2. 搜索用户的个人知识库，如果有相关内容则引用并提供链接

## 回答要求
- 回答要详细、有结构、有价值
- 如果上下文中包含知识库搜索结果，你必须基于这些结果来回答用户的问题，引用并标注来源路径
- 如果上下文中没有知识库搜索结果，直接用你的知识回答，不需要提及知识库
- 绝对不要说"没有找到相关内容"或"知识库中没有"之类的话 —— 要么用知识库结果回答，要么用你自己的知识回答
- 不要只说"已搜索"或"未找到"，要真正回答用户的问题
- 引用知识库条目时，使用 [[条目标题]] 格式创建链接，例如：详见 [[向量索引]]
"""


class ExtractedFact(BaseModel):
    """LLM 提取的单条结构化事实"""

    content: str = Field(description="事实内容，一句话，简洁明确")
    type: str = Field(
        default="unknown",
        description="事实类型：user_preference / user_habit / project_context / tech_constraint / task_goal",
    )
    scope: str = Field(
        default="session",
        description="作用域：user（跨session持久生效）/ session（仅当前session生效）",
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="置信度 0.0-1.0",
    )


class FactExtractionResult(BaseModel):
    """LLM 提取的全部事实"""

    facts: list[ExtractedFact] = Field(default_factory=list, description="提取的事实列表")


_fact_parser = PydanticOutputParser(pydantic_object=FactExtractionResult)

KEY_FACTS_PROMPT = """从以下对话上下文提取关键事实，并判断每个事实的作用域。

## 用户消息
{user_message}

## 对话历史摘要
{history_summary}

## 知识库搜索结果
{search_results}

## 现有 User Memory（跨 session 持久生效）
{user_memory}

## 现有 Session Memory（当前会话）
{session_memory}

## 事实类型与作用域规则

1. **user_preference** (scope: user) — 用户明确表达的个人偏好
   - "我喜欢 Python" / "我习惯用 vim" / "我偏好简洁的回答"

2. **user_habit** (scope: user) — 用户的行为习惯
   - "我习惯先写测试" / "我喜欢详细解释"

3. **project_context** (scope: session) — 当前项目的上下文
   - "这个项目使用 Java" / "我们用的是 MongoDB"

4. **tech_constraint** (scope: session) — 当前的技术约束
   - "必须兼容 Python 3.9" / "不能用外部依赖"

5. **task_goal** (scope: session) — 当前任务目标
   - "正在实现登录功能" / "需要优化查询性能"

## 重要规则

**只提取用户明确表达的事实性信息，不要提取以下内容：**
- 简单问候（"你好"、"你是谁"、"hi"、"hello"）
- 一般性问题（"什么是Python"、"如何使用Git"）
- 代码解释请求（"解释这段代码"、"这个函数怎么用"）
- 不包含用户偏好、习惯、项目上下文、技术约束或任务目标的消息

**如果用户消息不包含可提取的事实，返回空列表：**
{{"facts": []}}

## 冲突处理

如果新事实与现有 User Memory 矛盾：
- 如果是用户偏好变化（"以前喜欢 Java，现在喜欢 Python"）→ scope=user
- 如果是不同上下文（"公司用 Java，个人用 Python"）→ 两条都保留
- 如果不确定 → scope=session

{format_instructions}
"""

# 创建 LLM — 优先 ZhipuAI，兜底 DeepSeek
chat_llm = create_chat_llm(temperature=0.7, streaming=True)


def _chunk_text(chunk: object) -> str:
    """Extract text from AIMessageChunk / ChatGenerationChunk."""
    content = getattr(chunk, "content", None)
    if content is None and hasattr(chunk, "message"):
        content = getattr(chunk.message, "content", None)
    if content is None and hasattr(chunk, "text"):
        content = chunk.text
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return str(content)


class WikiState(TypedDict, total=False):
    """Wiki Agent 共享状态"""

    user_message: str
    wiki_results: list[dict]
    wiki_text: str | None
    ai_response: str
    decision: dict | None
    action_result: dict | None
    stage: str
    retrieved_context: dict | None
    eval_task_id: str | None  # 评估任务 ID（HITL resume 时复用）


def _get_configurable(config: RunnableConfig) -> dict:
    return (config or {}).get("configurable") or {}


def _build_llm_messages(state: WikiState, chat_history: list[BaseMessage]) -> list[BaseMessage]:
    """根据图状态与会话历史构建 LLM 消息列表（统一上下文块）"""
    user_message = state["user_message"]

    history = list(chat_history)
    if history and isinstance(history[-1], HumanMessage) and history[-1].content == user_message:
        prior = history[:-1]
    else:
        prior = history

    # 截断到最近 N 轮（chat.py 已截断，这里做二次保护）
    max_messages = settings.HISTORY_MAX_TURNS * 2
    truncated = len(prior) > max_messages
    if truncated:
        prior = prior[-max_messages:]

    ctx_data = state.get("retrieved_context")
    if ctx_data:
        ctx = RetrievedContext(
            wiki_results=ctx_data.get("wiki_results", []),
            user_facts=ctx_data.get("user_facts", []),
            session_facts=ctx_data.get("key_facts", []),
            history_summary=ctx_data.get("history_summary", ""),
        )
        context_block = build_context_block(ctx)
    else:
        context_block = ""
        wiki_text = state.get("wiki_text")
        if wiki_text:
            context_block = f"[知识库搜索结果]\n{wiki_text}"

    messages = [SystemMessage(content=SYSTEM_PROMPT)]

    if truncated:
        messages.append(SystemMessage(content=(
            f"注意：以下对话仅包含最近 {settings.HISTORY_MAX_TURNS} 轮。"
            "更早的对话上下文已在上方 [对话历史] 和 [会话记忆] 中摘要呈现。"
        )))

    if context_block:
        context_msg = (
            f"{context_block}\n\n"
            "请基于以上知识库搜索结果回答用户问题。"
            "引用结果中的具体内容，并在回答中标注来源路径。"
            "如果长期记忆中有相关事实，请确保回答与之一致。"
        )
        messages.append(SystemMessage(content=context_msg))

    messages.extend(prior)
    messages.append(HumanMessage(content=user_message))
    return messages


async def _emit(queue: asyncio.Queue | None, event: dict) -> None:
    if queue is not None:
        await queue.put(event)


# ── key_facts 提取（业务逻辑） ────────────────────────


async def _extract_key_facts(
    user_message: str,
    search_results: list[dict],
    chat_history: list[BaseMessage],
    session_id: str | None = None,
) -> tuple[list[dict], list[dict]]:
    """用 LLM 从对话上下文中提取结构化 key_facts。

    Returns:
        (session_facts, user_facts)
        - session_facts: list[dict]，存入当前 session 的 key_facts
        - user_facts: list[dict]，存入 User Memory（跨 session）
    """
    # 跳过简单查询和信息查询，不提取事实
    simple_patterns = [
        r'^(你好|hi|hello|hey|嗨|您好)',
        r'^(你是谁|你叫什么|who are you)',
        r'^(什么是|怎么用|如何|解释|说明)',
        r'^(谢谢|感谢|thanks)',
        r'^(再见|bye|拜拜)',
        r'^(总结|概述|列举|列出|介绍|描述|解释)',
        r'^(有哪些|有什么|包含什么|包括什么)',
        r'^(查询|搜索|查找|找)',
        r'^(帮我|请|能否|可以)',
    ]
    for pattern in simple_patterns:
        if re.match(pattern, user_message.strip(), re.IGNORECASE):
            return [], []

    history_summary = ""
    if chat_history:
        recent = chat_history[-6:]
        parts = []
        for msg in recent:
            role = "用户" if isinstance(msg, HumanMessage) else "助手"
            content = str(getattr(msg, "content", ""))[:200]
            parts.append(f"{role}: {content}")
        history_summary = "\n".join(parts)

    search_text = ""
    if search_results:
        search_text = "\n".join(f"- {r.get('title', '')}: {r.get('snippet', '')[:150]}" for r in search_results[:5])

    # 获取现有记忆用于冲突检测（并行读取）
    existing_user = []
    existing_session = []
    try:
        user_task = asyncio.create_task(session_store.get_user_memory())
        session_task = asyncio.create_task(session_store.get_session_key_facts(session_id)) if session_id else None

        existing_user = await user_task
        existing_session = await session_task if session_task else []
    except Exception:
        pass

    user_memory_text = "\n".join(f"- {f['content']}" for f in existing_user[:10] if isinstance(f, dict)) if existing_user else "无"
    session_memory_text = "\n".join(f"- {f['content']}" for f in existing_session[:10] if isinstance(f, dict)) if existing_session else "无"

    prompt = KEY_FACTS_PROMPT.format(
        user_message=user_message,
        history_summary=history_summary or "无",
        search_results=search_text or "无",
        user_memory=user_memory_text,
        session_memory=session_memory_text,
        format_instructions=_fact_parser.get_format_instructions(),
    )

    try:
        from langchain_core.messages import HumanMessage as HM

        _fact_llm = create_chat_llm(temperature=0, max_tokens=400)

        try:
            structured_llm = _fact_llm.with_structured_output(FactExtractionResult)
            result: FactExtractionResult = await structured_llm.ainvoke([HM(content=prompt)])
        except Exception:
            response = await _fact_llm.ainvoke([HM(content=prompt)])
            content = response.content or ""
            json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
            json_text = json_match.group(1) if json_match else content
            result = _fact_parser.parse(json_text)

        session_facts = []
        user_facts = []
        for f in result.facts:
            if not f.content:
                continue
            fact_dict = {
                "content": f.content,
                "type": f.type,
                "confidence": f.confidence,
            }
            if f.scope == "user":
                user_facts.append(fact_dict)
            else:
                session_facts.append(fact_dict)

        return session_facts[:5], user_facts[:5]

    except Exception as exc:
        print(f"[key_facts] 提取失败: {exc}")

    return [], []


# ── 计划生成（Plan-and-Execute）──────────────────────────────

from prompts import get_prompt


async def _generate_plan(user_message: str) -> dict:
    """LLM 根据用户问题生成执行计划。"""
    import json as _json
    import re as _re

    from app.wiki_agent.agent.llm_factory import create_chat_llm

    try:
        llm = create_chat_llm(temperature=0.3, max_tokens=500)
        prompt_text = get_prompt("wiki_agent/plan").format(
            user_message=user_message[:500], format_instructions=""
        )
        response = await llm.ainvoke([HumanMessage(content=prompt_text)])
        raw = (response.content or "").strip()

        m = _re.search(r'\{[\s\S]*\}', raw)
        if m:
            return _json.loads(m.group())
    except Exception as e:
        print(f"[Wiki Agent] 计划生成失败: {e}")

    return {
        "steps": [
            {"milestone": "search", "description": "检索知识库和四路记忆"},
            {"milestone": "respond", "description": "基于检索结果生成回复"},
            {"milestone": "decide", "description": "判断是否需要保存为知识条目"},
        ],
        "strategy": "标准知识助手流程",
    }


# ── 节点（纯业务逻辑） ──────────────────────────────────────


async def search(state: WikiState, config: RunnableConfig) -> WikiState:
    """统一检索四路记忆（KB + user_memory + session_memory + history）"""
    print("[Wiki Agent] 检索上下文...")
    collector = get_collector()
    state_before = {k: str(v)[:100] for k, v in state.items() if v}
    collector.record_node_execute("search", input_data=state_before)

    # LLM 生成初始计划（Plan-and-Execute 架构）
    user_msg = state["user_message"]
    plan = await _generate_plan(user_msg)
    collector.record(
        "plan",
        {
            "steps": plan.get("steps", []),
            "goal": user_msg[:200],
            "strategy": plan.get("strategy", ""),
        },
    )
    user_message = state["user_message"]
    configurable = _get_configurable(config)
    chat_history: list[BaseMessage] = configurable.get("chat_history") or []
    session_id = configurable.get("session_id")
    started = asyncio.get_running_loop().time()

    # 统一检索
    t0 = asyncio.get_running_loop().time()
    ctx = await retrieve_context(user_message, chat_history, session_id)
    t1 = asyncio.get_running_loop().time()
    print(f"[Timing] retrieve_context: {(t1-t0)*1000:.0f}ms")

    duration_ms = round((t1 - started) * 1000, 2)

    collector.record_retrieval(user_message, ctx.wiki_results, duration_ms=duration_ms)

    # wiki_text 向后兼容
    wiki_text = None
    if ctx.wiki_results:
        lines = [f"- {r['title']} ({r['path']}): {r['snippet']}" for r in ctx.wiki_results[:3]]
        wiki_text = "\n".join(lines)

    # 提取结构化 key_facts，按 scope 分流
    t2 = asyncio.get_running_loop().time()
    session_facts_raw, user_facts_raw = await _extract_key_facts(
        user_message, ctx.wiki_results, chat_history, session_id
    )
    t3 = asyncio.get_running_loop().time()
    print(f"[Timing] _extract_key_facts: {(t3-t2)*1000:.0f}ms")

    # 异步存储记忆（不阻塞主流程）
    async def _store_memories():
        try:
            if session_id and session_facts_raw:
                all_session_facts = await session_store.merge_session_key_facts(session_id, session_facts_raw)
                ctx.session_facts = all_session_facts
                print(f"[Session Memory] 新增 {len(session_facts_raw)} 条，累积 {len(all_session_facts)} 条")

            if user_facts_raw:
                all_user_facts = await session_store.merge_user_memory(user_facts_raw)
                ctx.user_facts = all_user_facts
                print(f"[User Memory] 新增 {len(user_facts_raw)} 条，累积 {len(all_user_facts)} 条")
        except Exception as e:
            print(f"[Memory] 异步存储失败: {e}")

    asyncio.create_task(_store_memories())

    if ctx.session_facts or ctx.user_facts:
        collector.record_memory_write(
            "key_facts",
            [f.get("content", "") for f in (ctx.session_facts + ctx.user_facts) if isinstance(f, dict)],
            source="llm_extraction",
            memory_type="fact",
        )

    # 记录 MEMORY_READ（读取记忆）
    if ctx.user_facts:
        collector.record_memory_read("user_memory", value=len(ctx.user_facts), context="search node", hit=True)
    if ctx.session_facts:
        collector.record_memory_read("session_memory", value=len(ctx.session_facts), context="search node", hit=True)

    # 日志
    context_block = build_context_block(ctx)
    print(
        f"[Context] wiki: {len(ctx.wiki_results)} docs, "
        f"user: {len(ctx.user_facts)} facts, "
        f"session: {len(ctx.session_facts)} facts, "
        f"history: {len(ctx.history_summary)} chars → {len(context_block)} chars"
    )

    # 记录 EVIDENCE（组装证据池）
    collector.record_evidence(
        evidence_type="rag_context",
        sources={
            "retrieved_docs": ctx.wiki_results,
            "memory_results": ctx.user_facts + ctx.session_facts,
            "chat_history_count": len(chat_history),
        },
        context=f"Query: {user_message[:100]}",
    )

    # 中间 flush — 确保搜索阶段的轨迹步骤已保存到数据库
    # （防止 finish() 未执行导致轨迹丢失）
    await collector._async_flush()

    # 记录 PLAN_UPDATE（基于检索结果的真正规划）
    has_kb_results = len(ctx.wiki_results) > 0
    has_memory = len(ctx.user_facts) > 0 or len(ctx.session_facts) > 0
    plan_steps = []
    if has_kb_results:
        plan_steps.append(f"引用知识库 {len(ctx.wiki_results)} 条结果回答")
    if has_memory:
        plan_steps.append("结合用户偏好和会话上下文")
    plan_steps.append("生成结构化回复")
    if len(user_message) > 20:
        plan_steps.append("分析是否需要保存为知识条目")

    collector.record_plan_update(
        milestone_status={
            "search": "done",
            "respond": "pending",
            "decide": "pending",
        },
        next_action="respond: 基于检索结果生成回复",
        reason=f"检索到 {len(ctx.wiki_results)} 条知识库结果，{'有' if has_memory else '无'}记忆数据",
        remaining_steps=plan_steps,
    )

    # 记录 NODE_COMPLETE + STATE_CHANGE
    state_after = {"wiki_results_count": len(ctx.wiki_results), "user_facts_count": len(ctx.user_facts), "session_facts_count": len(ctx.session_facts)}
    collector.record_node_execute("search_complete", output_data=state_after)
    collector.record_state_change(state_before, state_after, trigger="search", node_name="search")

    return {
        **state,
        "wiki_results": ctx.wiki_results,
        "wiki_text": wiki_text,
        "retrieved_context": {
            "wiki_results": ctx.wiki_results,
            "user_facts": ctx.user_facts,
            "key_facts": ctx.session_facts,
            "history_summary": ctx.history_summary,
        },
        "stage": "search",
        "eval_task_id": collector.task_id,  # 保存 task_id 供 HITL resume 复用
    }


async def respond(state: WikiState, config: RunnableConfig) -> WikiState:
    """流式或非流式生成回复"""
    print("[Wiki Agent] 生成回复...")
    collector = get_collector()
    state_before = {"ai_response": "", "stage": state.get("stage", "")}
    collector.record_node_execute("respond", input_data=state_before)
    t0 = asyncio.get_running_loop().time()
    configurable = _get_configurable(config)
    queue: asyncio.Queue | None = configurable.get("event_queue")
    chat_history: list[BaseMessage] = configurable.get("chat_history") or []
    session_id: str | None = configurable.get("session_id")

    wiki_text = state.get("wiki_text")
    if wiki_text:
        await _emit(queue, {"type": "wiki_results", "results": wiki_text})

    messages = _build_llm_messages(state, chat_history)
    collected = ""
    first_token_time = None

    async for chunk in chat_llm.astream(messages):
        text = _chunk_text(chunk)
        if not text:
            continue
        if first_token_time is None:
            first_token_time = asyncio.get_running_loop().time()
            print(f"[Timing] LLM first token: {(first_token_time-t0)*1000:.0f}ms")
        collected += text
        if queue is not None:
            await _emit(queue, {"type": "content", "text": text})

    if session_id:
        collector.record(ActionType.EVIDENCE, {"evidence_type": "final_answer", "final_response": collected[:4000], "session_id": session_id})

    # 记录 NODE_COMPLETE + STATE_CHANGE
    state_after = {"ai_response_len": len(collected), "stage": "respond"}
    collector.record_node_execute("respond_complete", output_data=state_after)
    collector.record_state_change(state_before, state_after, trigger="respond", node_name="respond")

    # 中间 flush — 确保回复阶段的轨迹步骤已保存
    await collector._async_flush()

    return {**state, "ai_response": collected, "stage": "respond"}


async def decide(state: WikiState, config: RunnableConfig) -> WikiState:
    """分析对话，决定知识库操作"""
    print("[Wiki Agent] 分析对话...")
    collector = get_collector()
    collector.record_node_execute("decide", input_data={"user_message": state["user_message"][:100]})
    configurable = _get_configurable(config)
    queue: asyncio.Queue | None = configurable.get("event_queue")

    user_message = state["user_message"]
    ai_response = state.get("ai_response", "")

    if not ai_response or len(ai_response) < 50:
        return {
            **state,
            "decision": {"action": "none", "reason": "回复太短"},
            "stage": "decide",
        }

    await _emit(queue, {"type": "status", "message": "正在分析对话内容..."})

    chat_history: list[BaseMessage] = configurable.get("chat_history") or []
    session_id: str | None = configurable.get("session_id")

    retrieved_context = state.get("retrieved_context", {})
    context_block = build_context_block_from_dict(retrieved_context) or "（无已有上下文）"

    decision = await knowledge_agent.decide_action(
        user_message, ai_response, chat_history, session_id,
        existing_context=context_block
    )
    decision_dict = decision.to_dict()

    if not decision_dict.get("title") and decision_dict.get("path"):
        stem = decision_dict["path"].replace(".md", "").split("/")[-1]
        decision_dict["title"] = stem

    # 记录 TOOL_DECISION（decide 节点决定执行什么操作）
    action = decision_dict.get("action", "none")
    if action != "none":
        collector.record(
            "tool_decision",
            {"node_name": "decide", "tool_name": f"crud_{action}", "input": {"title": decision_dict.get("title"), "path": decision_dict.get("path")}},
        )
        # 记录 PLAN_UPDATE（决定下一步操作 = 计划更新）
        collector.record_plan_update(
            milestone_status={"search": "done", "respond": "done", "decide": "done"},
            next_action=f"execute {action}",
            reason=decision_dict.get("reason", ""),
        )

    # 记录 STATE_CHANGE
    collector.record_node_execute("decide_complete", output_data={"action": action})
    collector.record_state_change(
        {"stage": "respond"},
        {"stage": "decide", "action": action},
        trigger="decide", node_name="decide",
    )

    return {**state, "decision": decision_dict, "stage": "decide"}


async def execute(state: WikiState, config: RunnableConfig) -> WikiState:
    """Human-in-the-Loop：等待用户确认后执行 CRUD"""
    collector = get_collector()
    collector.record_node_execute("execute", input_data={"decision": state.get("decision")})
    user_confirmed = interrupt({})

    if not user_confirmed:
        print("[Wiki Agent] 用户取消操作")
        # 记录 REPLAN（用户取消 = 改变计划）
        collector.record_replan(
            reason="用户取消了知识库操作",
            new_plan="跳过 CRUD，返回对话结果",
            trigger="user_cancel",
        )
        return {
            **state,
            "action_result": {"status": "cancelled", "message": "用户取消"},
            "stage": "execute",
        }

    decision = state.get("decision")
    if not decision or decision.get("action") == "none":
        return {**state, "action_result": None, "stage": "execute"}

    action = decision.get("action")
    print(f"[Wiki Agent] 用户确认，执行操作: {action}")

    import time as _time
    result = None
    tool_start = _time.monotonic()

    try:
        if action == "create":
            result = await asyncio.to_thread(
                crud_tools.create_knowledge,
                title=decision.get("title", ""),
                content=decision.get("content", ""),
                category=decision.get("category", ""),
                tags=decision.get("tags") or [],
            )
        elif action == "update":
            result = await asyncio.to_thread(
                crud_tools.update_knowledge,
                path=decision.get("path", ""),
                content=decision.get("content"),
                tags=decision.get("tags"),
            )
        elif action == "delete":
            result = await asyncio.to_thread(crud_tools.delete_knowledge, decision.get("path", ""))

        duration_ms = (_time.monotonic() - tool_start) * 1000

        # 记录 TOOL_CALL + TOOL_RESULT
        collector.record_tool_call(
            tool_name=f"crud_{action}",
            tool_input={"title": decision.get("title"), "path": decision.get("path")},
            tool_output=str(result)[:2000] if result else None,
            duration_ms=duration_ms,
        )
        collector.record_tool_result(
            tool_name=f"crud_{action}",
            tool_output=str(result)[:2000] if result else None,
            duration_ms=duration_ms,
            success=result.get("status") == "ok" if result else False,
        )

    except Exception as e:
        duration_ms = (_time.monotonic() - tool_start) * 1000
        # 记录 FAILURE
        collector.record_failure(
            error_type=type(e).__name__,
            error_message=str(e),
            context=f"CRUD operation '{action}' failed",
            recoverable=True,
            node_name="execute",
        )
        # 记录失败的 TOOL_CALL + TOOL_RESULT
        collector.record_tool_call(
            tool_name=f"crud_{action}",
            tool_input={"title": decision.get("title"), "path": decision.get("path")},
            tool_output=str(e)[:2000],
            duration_ms=duration_ms,
        )
        collector.record_tool_result(
            tool_name=f"crud_{action}",
            tool_output=str(e)[:2000],
            duration_ms=duration_ms,
            success=False,
            error_type=type(e).__name__,
        )

        # ── REPLAN：失败后尝试替代方案 ──
        replan_reason = f"{action} 失败: {str(e)[:100]}"
        alternative_action = None

        # 策略 1: create 失败（已存在）→ 尝试 update
        if action == "create" and "已存在" in str(e):
            alternative_action = "update"
            replan_reason += " → 尝试 update 替代"

        # 策略 2: update 失败（不存在）→ 尝试 create
        elif action == "update" and "不存在" in str(e):
            alternative_action = "create"
            replan_reason += " → 尝试 create 替代"

        # 记录 REPLAN
        collector.record_replan(
            reason=replan_reason,
            new_plan=f"尝试 {alternative_action}" if alternative_action else "返回错误",
            trigger=f"crud_{action}_failure",
        )

        # 尝试替代方案
        if alternative_action:
            print(f"[Wiki Agent] REPLAN: {replan_reason}")
            try:
                retry_start = _time.monotonic()
                if alternative_action == "update":
                    result = await asyncio.to_thread(
                        crud_tools.update_knowledge,
                        path=decision.get("path", ""),
                        content=decision.get("content"),
                        tags=decision.get("tags"),
                    )
                elif alternative_action == "create":
                    result = await asyncio.to_thread(
                        crud_tools.create_knowledge,
                        title=decision.get("title", ""),
                        content=decision.get("content", ""),
                        category=decision.get("category", ""),
                        tags=decision.get("tags") or [],
                    )
                retry_ms = (_time.monotonic() - retry_start) * 1000

                # 记录替代方案的 TOOL_CALL + TOOL_RESULT
                collector.record_tool_call(
                    tool_name=f"crud_{alternative_action}_retry",
                    tool_input={"title": decision.get("title"), "path": decision.get("path")},
                    tool_output=str(result)[:2000] if result else None,
                    duration_ms=retry_ms,
                )
                collector.record_tool_result(
                    tool_name=f"crud_{alternative_action}_retry",
                    tool_output=str(result)[:2000] if result else None,
                    duration_ms=retry_ms,
                    success=result.get("status") == "ok" if result else False,
                )
            except Exception as retry_e:
                result = {"status": "error", "message": f"替代方案也失败: {retry_e}"}
                collector.record_failure(
                    error_type=type(retry_e).__name__,
                    error_message=str(retry_e),
                    context=f"Retry {alternative_action} also failed",
                    recoverable=False,
                    node_name="execute",
                )
        else:
            result = {"status": "error", "message": str(e)}

    print(f"[Wiki Agent] 执行结果: {result}")
    return {**state, "action_result": result, "stage": "execute"}


def should_decide(state: WikiState) -> Literal["decide", "end"]:
    ai_response = state.get("ai_response", "")
    if ai_response and len(ai_response) > 50:
        return "decide"
    return "end"


def should_execute(state: WikiState) -> Literal["execute", "end"]:
    decision = state.get("decision")
    if decision and decision.get("action") != "none":
        return "execute"
    return "end"


def create_wiki_graph(checkpointer):
    """创建 wiki agent graph"""
    graph = StateGraph(WikiState)
    graph.add_node("search", search)
    graph.add_node("respond", respond)
    graph.add_node("decide", decide)
    graph.add_node("execute", execute)
    graph.set_entry_point("search")
    graph.add_edge("search", "respond")
    graph.add_conditional_edges("respond", should_decide, {"decide": "decide", "end": END})
    graph.add_conditional_edges("decide", should_execute, {"execute": "execute", "end": END})
    graph.add_edge("execute", END)
    compiled = graph.compile(checkpointer=checkpointer)
    return compiled


_wiki_graph = None


async def get_wiki_graph():
    global _wiki_graph
    if _wiki_graph is None:
        conn = await aiosqlite.connect(_CHECKPOINT_DB)
        checkpointer = AsyncSqliteSaver(conn=conn)
        _wiki_graph = create_wiki_graph(checkpointer)
    return _wiki_graph


def _extraction_from_result(result: dict, thread_id: str) -> dict | None:
    decision = result.get("decision")
    if not decision or decision.get("action") == "none":
        return None
    return {**decision, "thread_id": thread_id}


# ── 运行入口 ────────────────────────────────────────────────


async def run_chat_stream(
    user_message: str,
    chat_history: list[BaseMessage],
    *,
    session_id: str | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """经 LangGraph 运行完整对话流，产出 SSE 事件 dict"""
    graph = await get_wiki_graph()
    thread_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    collector = get_collector()
    await collector.start_async(user_message, {"thread_id": thread_id, "mode": "stream"})

    config: RunnableConfig = {
        "configurable": {
            "thread_id": thread_id,
            "event_queue": queue,
            "chat_history": chat_history,
            "session_id": session_id,
        }
    }

    initial_state: WikiState = {
        "user_message": user_message,
        "ai_response": "",
        "wiki_results": [],
        "wiki_text": None,
        "decision": None,
        "action_result": None,
        "stage": "",
        "retrieved_context": None,
    }

    _task_id = collector.task_id

    async def _run_graph():
        try:
            result = await graph.ainvoke(initial_state, config)
            extraction = _extraction_from_result(result, thread_id)
            if extraction:
                await queue.put({"type": "extraction", "data": extraction})
            await queue.put({"type": "_done", "result": result})
        except Exception as e:
            await queue.put({"type": "error", "message": str(e)})
        finally:
            await queue.put(None)

    task = asyncio.create_task(_run_graph())
    flow_completed = False  # 是否正常完成（非 HITL 中断）

    try:
        while True:
            event = await queue.get()
            if event is None:
                break
            if event.get("type") == "_done":
                flow_completed = True
                break
            yield event
    finally:
        print(f"[EvalDiag] run_chat_stream finally block entered, task_id={_task_id} flow_completed={flow_completed}")
        if flow_completed:
            # 正常完成 → flush + 触发评估
            await collector.finish_async(auto_run=True)
            print(f"[EvalDiag] finish_async returned task_id={_task_id}")
        else:
            # HITL 中断或异常 → 只 flush，不触发评估
            await collector._async_flush()
            print(f"[Wiki Agent] HITL interrupt, task {_task_id} paused, waiting for resume")
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


async def _find_task_by_thread_id(thread_id: str) -> str | None:
    """通过 thread_id 在数据库中查找已有的 task。

    collector.start() 创建 task 时会把 thread_id 存在 context 中。
    这里通过 API 查询匹配的 task。
    """
    import httpx

    from sdk.collector import _env_str

    api_base = _env_str("EVAL_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    try:
        r = httpx.get(f"{api_base}/api/v1/tasks/", params={"limit": 50}, timeout=5.0)
        if r.status_code == 200:
            tasks = r.json()
            for task in tasks:
                ctx = task.get("context") or {}
                if isinstance(ctx, str):
                    import json
                    try:
                        ctx = json.loads(ctx)
                    except Exception:
                        continue
                if ctx.get("thread_id") == thread_id:
                    return task["id"]
    except Exception as e:
        print(f"[Wiki Agent] 查找已有 task 失败: {e}")
    return None


async def run_chat_invoke(
    user_message: str,
    chat_history: list[BaseMessage],
    *,
    session_id: str | None = None,
) -> dict[str, Any]:
    """非流式：经 LangGraph 完成 search → respond → decide（至 interrupt 或结束）"""
    graph = await get_wiki_graph()
    thread_id = str(uuid.uuid4())
    collector = get_collector()
    await collector.start_async(user_message, {"thread_id": thread_id, "mode": "invoke"})

    config: RunnableConfig = {
        "configurable": {
            "thread_id": thread_id,
            "event_queue": None,
            "chat_history": chat_history,
            "session_id": session_id,
        }
    }
    initial_state: WikiState = {
        "user_message": user_message,
        "ai_response": "",
        "wiki_results": [],
        "wiki_text": None,
        "decision": None,
        "action_result": None,
        "stage": "",
        "retrieved_context": None,
    }
    try:
        result = await graph.ainvoke(initial_state, config)
    except Exception:
        await collector.finish_async(auto_run=True)
        raise
    await collector.finish_async(auto_run=True)
    return {
        "content": result.get("ai_response", ""),
        "wiki_text": result.get("wiki_text"),
        "extraction": _extraction_from_result(result, thread_id),
    }


async def resume_and_execute(
    thread_id: str,
    confirm: bool,
    *,
    session_id: str | None = None,
) -> dict:
    """从 checkpoint 恢复，执行或取消知识库操作。

    通过 collector.attach() 将后续步骤附加到第一次请求创建的 task 上，
    确保 HITL 流程的完整轨迹（search→respond→decide→execute）记录在同一个 task 中。
    """
    graph = await get_wiki_graph()

    # 从 LangGraph checkpoint 恢复时，attach 到第一次请求创建的 task
    collector = get_collector()
    if not collector.task_id:
        # 从 checkpoint 中读取第一次请求保存的 eval_task_id
        existing_task_id = None
        try:
            state_snapshot = await graph.aget_state({"configurable": {"thread_id": thread_id}})
            if state_snapshot and state_snapshot.values:
                existing_task_id = state_snapshot.values.get("eval_task_id")
        except Exception as e:
            print(f"[Wiki Agent] 读取 checkpoint state 失败: {e}")

        if existing_task_id:
            collector.attach(existing_task_id)
            print(f"[Wiki Agent] HITL resume: attached to existing task {existing_task_id}")
        else:
            # checkpoint 中没有 task_id，尝试数据库查找
            existing_task_id = await _find_task_by_thread_id(thread_id)
            if existing_task_id:
                collector.attach(existing_task_id)
                print(f"[Wiki Agent] HITL resume: attached via DB lookup {existing_task_id}")
            else:
                await collector.start_async(f"resume:{thread_id}", {"thread_id": thread_id, "mode": "resume"})
                print(f"[Wiki Agent] HITL resume: created new task {collector.task_id}")

    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

    try:
        result = await graph.ainvoke(Command(resume=confirm), config)
    except Exception:
        await collector.finish_async(auto_run=True)
        raise
    await collector.finish_async(auto_run=True)

    action_result = result.get("action_result")
    decision = result.get("decision", {})

    if action_result and action_result.get("status") == "cancelled":
        return {
            "status": "cancelled",
            "message": "用户取消操作",
            "decision": decision,
        }

    return {
        "status": "ok",
        "decision": decision,
        "result": action_result,
    }
