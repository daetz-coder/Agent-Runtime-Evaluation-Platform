"""Wiki Agent — LangGraph 编排（search → respond → decide → execute）"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncGenerator
from typing import Any, Literal, TypedDict

import aiosqlite
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt

from app.agent import knowledge_agent
from app.agent.tools import crud_tools, search_tools
from app.agent.context_retriever import RetrievedContext, retrieve_context, build_context_block
from app.config import settings
from app.evaluation import EvaluationTrace, get_eval_trace
from app.session import store as session_store

_CHECKPOINT_DB = os.path.join(os.path.dirname(settings.DB_PATH), "checkpoints.db")
os.makedirs(os.path.dirname(_CHECKPOINT_DB), exist_ok=True)

SYSTEM_PROMPT = """你是一个智能知识助手。请用中文回答。

## 你的能力
1. 用你的知识详细回答用户的各种问题
2. 搜索用户的个人知识库，如果有相关内容则引用并提供链接

## 回答要求
- 回答要详细、有结构、有价值
- 如果知识库有相关内容，在回答中引用并标注来源路径
- 如果知识库没有相关内容，直接用你的知识回答，不需要提及知识库
- 不要只说"已搜索"或"未找到"，要真正回答用户的问题
"""

KEY_FACTS_PROMPT = """从以下对话上下文提取 Agent 必须记住的关键事实（key_facts）。
要求：
- 每条事实简洁明确，一句话
- 最多 5 条，只保留真正重要的
- 包括：用户偏好、项目技术栈、重要约束、已确认的事实
- 如果没有明确的关键事实，返回空数组

## 用户消息
{user_message}

## 对话历史摘要
{history_summary}

## 知识库搜索结果
{search_results}

## 输出格式
仅返回 JSON 数组，不要其他内容：
["事实1", "事实2", ...]
"""

TASK_CONTINUITY_PROMPT = """判断用户的新消息是对当前任务的「继续/追问/修改」还是一个「全新的任务」。

## 当前任务目标
{current_goal}

## 用户新消息
{new_message}

## 输出
仅返回一个词：
- "continue" — 如果新消息是在追问、补充、修改当前任务
- "new" — 如果新消息是一个完全不同的话题/任务
"""

chat_llm = ChatOpenAI(
    model=settings.ZHIPUAI_CHAT_MODEL,
    api_key=settings.ZHIPUAI_API_KEY,
    base_url=settings.ZHIPUAI_BASE_URL,
    temperature=0.7,
    streaming=True,
)


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


def _get_configurable(config: RunnableConfig) -> dict:
    """
    Get the configurable from the config.
    :param config: The config.
    :return: The configurable.
    """
    return (config or {}).get("configurable") or {}


def _build_llm_messages(state: WikiState, chat_history: list[BaseMessage]) -> list[BaseMessage]:
    """根据图状态与会话历史构建 LLM 消息列表（统一上下文块）"""
    user_message = state["user_message"]

    # 历史消息（去掉与当前 user_message 重复的最后一条）
    history = list(chat_history)
    if history and isinstance(history[-1], HumanMessage) and history[-1].content == user_message:
        prior = history[:-1]
    else:
        prior = history

    # 构建统一上下文块
    ctx_data = state.get("retrieved_context")
    if ctx_data:
        ctx = RetrievedContext(
            wiki_results=ctx_data.get("wiki_results", []),
            key_facts=ctx_data.get("key_facts", []),
            history_summary=ctx_data.get("history_summary", ""),
        )
        context_block = build_context_block(ctx)
    else:
        # 向后兼容：无 retrieved_context 时用旧 wiki_text
        context_block = ""
        wiki_text = state.get("wiki_text")
        if wiki_text:
            context_block = f"[知识库搜索结果]\n{wiki_text}"

    messages = [SystemMessage(content=SYSTEM_PROMPT)]

    if context_block:
        context_msg = (
            f"{context_block}\n\n"
            "请结合以上上下文回答用户问题。如果知识库有相关内容，在回答中标注来源路径。"
            "如果长期记忆中有相关事实，请确保回答与之一致。"
        )
        messages.append(SystemMessage(content=context_msg))

    messages.extend(prior)
    messages.append(HumanMessage(content=user_message))
    return messages


async def _emit(queue: asyncio.Queue | None, event: dict) -> None:
    if queue is not None:
        await queue.put(event)


# ── key_facts 提取 ────────────────────────────────────────────


async def _check_task_continuity(
    current_goal: str,
    new_message: str,
) -> bool:
    """判断新消息是继续当前任务（True）还是新任务（False）。"""
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage as HM

    prompt = TASK_CONTINUITY_PROMPT.format(
        current_goal=current_goal,
        new_message=new_message,
    )

    try:
        llm = ChatOpenAI(
            model=settings.ZHIPUAI_CHAT_MODEL,
            api_key=settings.ZHIPUAI_API_KEY,
            base_url=settings.ZHIPUAI_BASE_URL,
            temperature=0,
            max_tokens=10,
        )
        response = await llm.ainvoke([HM(content=prompt)])
        result = (response.content or "").strip().lower()
        return "continue" in result
    except Exception as exc:
        print(f"[continuity] 判断失败，默认新任务: {exc}")
        return False


async def _extract_key_facts(
    user_message: str,
    search_results: list[dict],
    chat_history: list[BaseMessage],
) -> list[str]:
    """用 LLM 从对话上下文中提取 key_facts（轻量调用）。"""
    import json as _json

    # 构建历史摘要（最近 6 条）
    history_summary = ""
    if chat_history:
        recent = chat_history[-6:]
        parts = []
        for msg in recent:
            role = "用户" if isinstance(msg, HumanMessage) else "助手"
            content = str(getattr(msg, "content", ""))[:200]
            parts.append(f"{role}: {content}")
        history_summary = "\n".join(parts)

    # 搜索结果摘要
    search_text = ""
    if search_results:
        search_text = "\n".join(
            f"- {r.get('title', '')}: {r.get('snippet', '')[:150]}"
            for r in search_results[:5]
        )

    prompt = KEY_FACTS_PROMPT.format(
        user_message=user_message,
        history_summary=history_summary or "无",
        search_results=search_text or "无",
    )

    try:
        # 使用轻量 LLM（temperature=0，短回复）
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage as HM

        llm = ChatOpenAI(
            model=settings.ZHIPUAI_CHAT_MODEL,
            api_key=settings.ZHIPUAI_API_KEY,
            base_url=settings.ZHIPUAI_BASE_URL,
            temperature=0,
            max_tokens=200,
        )
        response = await llm.ainvoke([HM(content=prompt)])
        content = response.content or ""

        # 解析 JSON 数组
        start = content.find("[")
        end = content.rfind("]") + 1
        if start != -1 and end > start:
            facts = _json.loads(content[start:end])
            if isinstance(facts, list):
                return [str(f) for f in facts if f][:5]
    except Exception as exc:
        print(f"[key_facts] 提取失败: {exc}")

    return []


# ── 节点 ──────────────────────────────────────────────────────


async def search(state: WikiState, config: RunnableConfig) -> WikiState:
    """统一检索三路记忆（KB + key_facts + history）"""
    print("[Wiki Agent] 检索上下文...")
    user_message = state["user_message"]
    configurable = _get_configurable(config)
    chat_history: list[BaseMessage] = configurable.get("chat_history") or []
    session_id = configurable.get("session_id")
    trace = get_eval_trace(config)
    started = asyncio.get_running_loop().time()

    # 统一检索
    ctx = await retrieve_context(user_message, chat_history, session_id)

    # wiki_text 向后兼容
    wiki_text = None
    if ctx.wiki_results:
        lines = [f"- {r['title']} ({r['path']}): {r['snippet']}" for r in ctx.wiki_results[:3]]
        wiki_text = "\n".join(lines)

    if trace:
        trace.record_tool_call(
            "hybrid_search",
            {"query": user_message, "limit": 3},
            {
                "result_count": len(ctx.wiki_results),
                "results": ctx.wiki_results,
                "wiki_text": wiki_text,
            },
            duration_ms=round((asyncio.get_running_loop().time() - started) * 1000, 2),
            call_id=f"hybrid_search:{user_message}",
        )

        # 提取新 key_facts 并累积到 session
        new_facts = await _extract_key_facts(user_message, ctx.wiki_results, chat_history)
        if session_id:
            all_facts = await session_store.merge_session_key_facts(session_id, new_facts)
            ctx.key_facts = all_facts  # 更新为完整列表
            await trace.update_context({"key_facts": all_facts})
            if new_facts:
                print(f"[key_facts] 新增 {len(new_facts)} 条，累积 {len(all_facts)} 条")

    # 日志
    context_block = build_context_block(ctx)
    print(f"[Context] wiki: {len(ctx.wiki_results)} docs, facts: {len(ctx.key_facts)}, "
          f"history: {len(ctx.history_summary)} chars → {len(context_block)} chars")

    return {
        **state,
        "wiki_results": ctx.wiki_results,
        "wiki_text": wiki_text,
        "retrieved_context": {
            "wiki_results": ctx.wiki_results,
            "key_facts": ctx.key_facts,
            "history_summary": ctx.history_summary,
        },
        "stage": "search",
    }


async def respond(state: WikiState, config: RunnableConfig) -> WikiState:
    """流式或非流式生成回复"""
    print("[Wiki Agent] 生成回复...")
    configurable = _get_configurable(config)
    queue: asyncio.Queue | None = configurable.get("event_queue")
    chat_history: list[BaseMessage] = configurable.get("chat_history") or []
    trace = get_eval_trace(config)

    wiki_text = state.get("wiki_text")
    if wiki_text:
        await _emit(queue, {"type": "wiki_results", "results": wiki_text})

    messages = _build_llm_messages(state, chat_history)
    collected = ""
    started = asyncio.get_running_loop().time()

    try:
        if queue is not None:
            async for chunk in chat_llm.astream(messages):
                if chunk.content:
                    collected += chunk.content
                    await _emit(queue, {"type": "content", "text": chunk.content})
        else:
            response = await chat_llm.ainvoke(messages)
            collected = response.content or ""
    finally:
        if trace:
            trace.record(
                "llm_call",
                {
                    "model": settings.ZHIPUAI_CHAT_MODEL,
                    "streaming": queue is not None,
                    "messages": [
                        {
                            "role": getattr(message, "type", "unknown"),
                            "content": str(getattr(message, "content", "")),
                        }
                        for message in messages
                    ],
                    "duration_ms": round((asyncio.get_running_loop().time() - started) * 1000, 2),
                    "response_chars": len(collected),
                },
                observation=collected,
            )

    return {**state, "ai_response": collected, "stage": "respond"}


async def decide(state: WikiState, config: RunnableConfig) -> WikiState:
    """分析对话，决定知识库操作"""
    print("[Wiki Agent] 分析对话...")
    configurable = _get_configurable(config)
    queue: asyncio.Queue | None = configurable.get("event_queue")
    trace = get_eval_trace(config)

    user_message = state["user_message"]
    ai_response = state.get("ai_response", "")

    if not ai_response or len(ai_response) < 50:
        return {
            **state,
            "decision": {"action": "none", "reason": "回复太短"},
            "stage": "decide",
        }

    await _emit(queue, {"type": "status", "message": "正在分析对话内容..."})

    started = asyncio.get_running_loop().time()
    decision = await knowledge_agent.decide_action(user_message, ai_response)
    decision_dict = decision.to_dict()

    if not decision_dict.get("title") and decision_dict.get("path"):
        stem = decision_dict["path"].replace(".md", "").split("/")[-1]
        decision_dict["title"] = stem

    if trace:
        trace.record(
            "think",
            {
                "thought": "Knowledge update decision completed",
                "decision": decision_dict,
                "duration_ms": round((asyncio.get_running_loop().time() - started) * 1000, 2),
            },
            observation=decision_dict.get("reason"),
        )

    return {**state, "decision": decision_dict, "stage": "decide"}


async def execute(state: WikiState, config: RunnableConfig) -> WikiState:
    """Human-in-the-Loop：等待用户确认后执行 CRUD"""
    trace = get_eval_trace(config)
    user_confirmed = interrupt({})

    if not user_confirmed:
        print("[Wiki Agent] 用户取消操作")
        if trace:
            trace.record("think", {"thought": "User cancelled knowledge-base action"})
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

    started = asyncio.get_running_loop().time()
    result = None
    if action == "create":
        result = crud_tools.create_knowledge(
            title=decision.get("title", ""),
            content=decision.get("content", ""),
            category=decision.get("category", ""),
            tags=decision.get("tags") or [],
        )
    elif action == "update":
        result = crud_tools.update_knowledge(
            path=decision.get("path", ""),
            content=decision.get("content"),
            tags=decision.get("tags"),
        )
    elif action == "delete":
        result = crud_tools.delete_knowledge(decision.get("path", ""))

    print(f"[Wiki Agent] 执行结果: {result}")
    if trace:
        trace.record_tool_call(
            f"wiki_{action}",
            {
                "title": decision.get("title"),
                "path": decision.get("path"),
                "category": decision.get("category"),
                "tags": decision.get("tags") or [],
            },
            result,
            duration_ms=round((asyncio.get_running_loop().time() - started) * 1000, 2),
            call_id=f"{action}:{decision.get('path') or decision.get('title')}",
        )
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
    """
    Create the wiki agent graph.
    :param checkpointer: The checkpointer.
    :return: The wiki agent graph.
    """
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
    return graph.compile(checkpointer=checkpointer)


_wiki_graph = None


async def get_wiki_graph():
    """
    Get the wiki agent graph.
    :return: The wiki agent graph.
    """
    global _wiki_graph
    if _wiki_graph is None:
        conn = await aiosqlite.connect(_CHECKPOINT_DB)
        checkpointer = AsyncSqliteSaver(conn=conn)
        _wiki_graph = create_wiki_graph(checkpointer)
    return _wiki_graph


def _extraction_from_result(result: dict, thread_id: str) -> dict | None:
    """
    Get the extraction from the result.
    :param result: The result.
    :param thread_id: The thread id.
    :return: The extraction.
    """
    decision = result.get("decision")
    if not decision or decision.get("action") == "none":
        return None
    return {**decision, "thread_id": thread_id}


async def _setup_eval_trace(
    user_message: str,
    session_id: str | None,
    mode: str,
    **extra_context,
) -> tuple[EvaluationTrace, str]:
    """创建或续接评估 trace，返回 (trace, eval_task_id)。"""
    trace = EvaluationTrace()

    # 检查是否有活跃的 task 可以续接
    if session_id:
        active_task_id = await session_store.get_active_eval_task_id(session_id)
        if active_task_id:
            # 用最近一条用户消息作为 current_goal 的近似
            is_continuation = await _check_task_continuity(
                current_goal="previous conversation",
                new_message=user_message,
            )
            if is_continuation:
                trace.resume(active_task_id)
                print(f"[Eval] 续接任务 {active_task_id[:8]}...")
                return trace, active_task_id

    # 新任务
    eval_task_id = await trace.start(
        user_message,
        {
            "agent": "example/wiki-agent",
            "mode": mode,
            "session_id": session_id,
            **extra_context,
        },
    )

    # 记录为 session 的活跃 task
    if session_id and eval_task_id:
        await session_store.set_active_eval_task_id(session_id, eval_task_id)

    return trace, eval_task_id


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

    trace, eval_task_id = await _setup_eval_trace(
        user_message, session_id, "stream",
        thread_id=thread_id,
        history_count=len(chat_history),
    )

    config: RunnableConfig = {
        "configurable": {
            "thread_id": thread_id,
            "event_queue": queue,
            "chat_history": chat_history,
            "eval_trace": trace,
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

    async def _run_graph():
        try:
            await queue.put({"type": "evaluation_task", "task_id": eval_task_id})
            result = await graph.ainvoke(initial_state, config)
            extraction = _extraction_from_result(result, thread_id)
            if extraction:
                await queue.put({"type": "extraction", "data": extraction})
            await trace.finish()
            await queue.put({"type": "_done", "result": result})
        except Exception as e:
            trace.record("think", {"thought": "Wiki graph failed", "error_type": type(e).__name__}, str(e))
            await trace.finish(auto_run=False)
            await queue.put({"type": "error", "message": str(e)})
        finally:
            await queue.put(None)

    task = asyncio.create_task(_run_graph())

    try:
        while True:
            event = await queue.get()
            if event is None:
                break
            if event.get("type") == "_done":
                break
            yield event
    finally:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


async def run_chat_invoke(
    user_message: str,
    chat_history: list[BaseMessage],
    *,
    session_id: str | None = None,
) -> dict[str, Any]:
    """非流式：经 LangGraph 完成 search → respond → decide（至 interrupt 或结束）"""
    graph = await get_wiki_graph()
    thread_id = str(uuid.uuid4())

    trace, eval_task_id = await _setup_eval_trace(
        user_message, session_id, "invoke",
        thread_id=thread_id,
        history_count=len(chat_history),
    )

    config: RunnableConfig = {
        "configurable": {
            "thread_id": thread_id,
            "event_queue": None,
            "chat_history": chat_history,
            "eval_trace": trace,
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
    except Exception as exc:
        trace.record("think", {"thought": "Wiki graph failed", "error_type": type(exc).__name__}, str(exc))
        await trace.finish(auto_run=False)
        raise
    await trace.finish()
    return {
        "content": result.get("ai_response", ""),
        "wiki_text": result.get("wiki_text"),
        "extraction": _extraction_from_result(result, thread_id),
        "evaluation_task_id": eval_task_id,
    }


async def resume_and_execute(thread_id: str, confirm: bool) -> dict:
    """从 checkpoint 恢复，执行或取消知识库操作"""
    graph = await get_wiki_graph()
    trace = EvaluationTrace()
    eval_task_id = await trace.start(
        f"{'Confirm' if confirm else 'Cancel'} pending wiki knowledge-base action",
        {
            "agent": "example/wiki-agent",
            "mode": "resume",
            "thread_id": thread_id,
            "confirm": confirm,
        },
    )
    config: RunnableConfig = {"configurable": {"thread_id": thread_id, "eval_trace": trace}}

    try:
        result = await graph.ainvoke(Command(resume=confirm), config)
    except Exception as exc:
        trace.record("think", {"thought": "Wiki resume failed", "error_type": type(exc).__name__}, str(exc))
        await trace.finish(auto_run=False)
        raise
    await trace.finish()

    action_result = result.get("action_result")
    decision = result.get("decision", {})

    if action_result and action_result.get("status") == "cancelled":
        return {
            "status": "cancelled",
            "message": "用户取消操作",
            "decision": decision,
            "evaluation_task_id": eval_task_id,
        }

    return {
        "status": "ok",
        "decision": decision,
        "result": action_result,
        "evaluation_task_id": eval_task_id,
    }
