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

from app.wiki_agent.agent import knowledge_agent
from app.wiki_agent.agent.tools import crud_tools, search_tools
from app.wiki_agent.config import settings
from app.wiki_agent.evaluation import EvaluationTrace, get_eval_trace

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

_chat_llm: ChatOpenAI | None = None


def _get_chat_llm() -> ChatOpenAI:
    global _chat_llm
    if _chat_llm is None:
        _chat_llm = ChatOpenAI(
            model=settings.DEEPSEEK_MODEL,
            api_key=settings.DEEPSEEK_API_KEY or "placeholder",
            base_url=settings.DEEPSEEK_BASE_URL,
            temperature=0.7,
            streaming=True,
        )
    return _chat_llm


class WikiState(TypedDict, total=False):
    """Wiki Agent 共享状态"""
    user_message: str
    wiki_results: list[dict]
    wiki_text: str | None
    ai_response: str
    decision: dict | None
    action_result: dict | None
    stage: str


def _get_configurable(config: RunnableConfig) -> dict:
    """
    Get the configurable from the config.
    :param config: The config.
    :return: The configurable.
    """
    return (config or {}).get("configurable") or {}


def _build_llm_messages(state: WikiState, chat_history: list[BaseMessage]) -> list[BaseMessage]:
    """根据图状态与会话历史构建 LLM 消息列表"""
    user_message = state["user_message"]
    wiki_text = state.get("wiki_text")

    history = list(chat_history)
    if history and isinstance(history[-1], HumanMessage) and history[-1].content == user_message:
        prior = history[:-1]
    else:
        prior = history

    if wiki_text:
        context_msg = (
            f"[知识库搜索结果]\n{wiki_text}\n\n"
            "请结合以上知识库内容回答用户问题。如果知识库有相关内容，在回答中标注来源路径。"
        )
        return [
            SystemMessage(content=SYSTEM_PROMPT),
            *prior,
            SystemMessage(content=context_msg),
            HumanMessage(content=user_message),
        ]
    return [SystemMessage(content=SYSTEM_PROMPT), *prior, HumanMessage(content=user_message)]


async def _emit(queue: asyncio.Queue | None, event: dict) -> None:
    if queue is not None:
        await queue.put(event)


# ── 节点 ──────────────────────────────────────────────────────


async def search(state: WikiState, config: RunnableConfig) -> WikiState:
    """混合检索知识库"""
    print("[Wiki Agent] 搜索知识库...")
    user_message = state["user_message"]
    trace = get_eval_trace(config)
    started = asyncio.get_running_loop().time()
    results = search_tools.hybrid_search(user_message, limit=3)

    wiki_text = None
    if results:
        lines = [f"- {r['title']} ({r['path']}): {r['snippet']}" for r in results[:3]]
        wiki_text = "\n".join(lines)

    if trace:
        trace.record_tool_call(
            "hybrid_search",
            {"query": user_message, "limit": 3},
            {
                "result_count": len(results),
                "results": results,
                "wiki_text": wiki_text,
            },
            duration_ms=round((asyncio.get_running_loop().time() - started) * 1000, 2),
            call_id=f"hybrid_search:{user_message}",
        )

    return {
        **state,
        "wiki_results": results,
        "wiki_text": wiki_text,
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
            async for chunk in _get_chat_llm().astream(messages):
                if chunk.content:
                    collected += chunk.content
                    await _emit(queue, {"type": "content", "text": chunk.content})
        else:
            response = await _get_chat_llm().ainvoke(messages)
            collected = response.content or ""
    finally:
        if trace:
            trace.record(
                "llm_call",
                {
                    "model": settings.DEEPSEEK_MODEL,
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
    trace = EvaluationTrace()
    eval_task_id = await trace.start(
        user_message,
        {
            "agent": "example/wiki-agent",
            "mode": "stream",
            "session_id": session_id,
            "thread_id": thread_id,
            "history_count": len(chat_history),
        },
    )

    config: RunnableConfig = {
        "configurable": {
            "thread_id": thread_id,
            "event_queue": queue,
            "chat_history": chat_history,
            "eval_trace": trace,
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
    trace = EvaluationTrace()
    eval_task_id = await trace.start(
        user_message,
        {
            "agent": "example/wiki-agent",
            "mode": "invoke",
            "session_id": session_id,
            "thread_id": thread_id,
            "history_count": len(chat_history),
        },
    )
    config: RunnableConfig = {
        "configurable": {
            "thread_id": thread_id,
            "event_queue": None,
            "chat_history": chat_history,
            "eval_trace": trace,
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
