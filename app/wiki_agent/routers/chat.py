"""对话 API — Wiki Agent 统一服务（LangGraph 编排）"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

from app.wiki_agent.agent.graph import resume_and_execute, run_chat_invoke, run_chat_stream
from app.wiki_agent.agent.tools import crud_tools
from app.wiki_agent.config import settings
from app.wiki_agent.session import store as session_store

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    session_id: str = "default"
    message: str


class SaveKnowledgeRequest(BaseModel):
    action: str  # "create" | "update" | "delete"
    title: str = ""
    category: str = ""
    content: str = ""
    target_path: str | None = None
    tags: list[str] = []


class ConfirmRequest(BaseModel):
    thread_id: str
    confirm: bool
    session_id: str | None = None


async def _ensure_session(session_id: str):
    """
    If id doesn't exist, create a new session
    :param session_id:
    :return:
    """
    if not await session_store.session_exists(session_id):
        await session_store.create_session(session_id)


def _build_history(messages: list[dict], max_turns: int | None = None) -> list:
    """将消息转为 LangChain 消息列表，最多保留最近 max_turns 轮。

    Args:
        messages: 原始消息列表（role/content）
        max_turns: 最大轮数（每轮 = user + assistant），默认取 settings.HISTORY_MAX_TURNS
    """
    if max_turns is None:
        max_turns = settings.HISTORY_MAX_TURNS
    # 每轮 2 条消息，保留最近 max_turns * 2 条
    recent = messages[-(max_turns * 2):] if max_turns > 0 else messages
    history = []
    for msg in recent:
        if msg["role"] == "user":
            history.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant" and msg["content"]:
            history.append(AIMessage(content=msg["content"]))
    return history


async def stream_response(session_id: str, user_message: str) -> AsyncGenerator[str, None]:
    """
    This function is used to stream the response from the LangGraph.
    :param session_id: The session id.
    :param user_message: The user message.
    :return: The stream response.
    """
    import asyncio
    total_start = asyncio.get_running_loop().time()

    await _ensure_session(session_id)

    # 只加载最近 N 轮消息构建 history，避免全量加载
    max_messages = settings.HISTORY_MAX_TURNS * 2
    recent_messages = await session_store.get_recent_messages(session_id, max_messages)
    history = _build_history(recent_messages)
    history.append(HumanMessage(content=user_message))

    await session_store.add_message(session_id, "user", user_message)

    if not recent_messages:
        name = user_message[:30] + ("..." if len(user_message) > 30 else "")
        await session_store.update_session_name(session_id, name)

    collected = ""
    wiki_text = None
    extraction_data = None

    try:
        first_content = True
        async for event in run_chat_stream(user_message, history, session_id=session_id):
            event_type = event.get("type")
            if event_type == "content":
                if first_content:
                    first_content = False
                    elapsed = asyncio.get_running_loop().time() - total_start
                    print(f"[Timing] Total time to first content: {elapsed*1000:.0f}ms")
                collected += event.get("text", "")
            elif event_type == "wiki_results":
                wiki_text = event.get("results")
            elif event_type == "extraction":
                extraction_data = event.get("data")
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    await session_store.add_message(
        session_id,
        "assistant",
        collected,
        wiki_results=wiki_text,
        extraction=extraction_data,
    )

    # 返回评估任务 ID（前端用于跳转评估详情页）
    from sdk.collector import get_collector
    eval_task_id = get_collector().task_id
    if eval_task_id:
        yield f"data: {json.dumps({'type': 'evaluation_task', 'task_id': eval_task_id}, ensure_ascii=False)}\n\n"

    yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"


@router.post("/stream")
async def chat_stream(req: ChatRequest):
    """SSE 流式对话"""
    return StreamingResponse(
        stream_response(req.session_id, req.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/message")
async def chat_message(req: ChatRequest):
    """非流式对话 — 同样经 LangGraph 编排"""
    await _ensure_session(req.session_id)

    # 只加载最近 N 轮消息构建 history，避免全量加载
    max_messages = settings.HISTORY_MAX_TURNS * 2
    recent_messages = await session_store.get_recent_messages(req.session_id, max_messages)
    history = _build_history(recent_messages)
    history.append(HumanMessage(content=req.message))

    await session_store.add_message(req.session_id, "user", req.message)

    if not recent_messages:
        name = req.message[:30] + ("..." if len(req.message) > 30 else "")
        await session_store.update_session_name(req.session_id, name)

    try:
        result = await run_chat_invoke(req.message, history, session_id=req.session_id)
        await session_store.add_message(
            req.session_id,
            "assistant",
            result["content"],
            wiki_results=result.get("wiki_text"),
            extraction=result.get("extraction"),
        )
        return {
            "content": result["content"],
            "wiki_results": result.get("wiki_text"),
            "extraction": result.get("extraction"),
        }
    except Exception as e:
        raise HTTPException(500, f"LLM 调用失败: {e}")


@router.post("/save-knowledge")
async def save_knowledge(req: SaveKnowledgeRequest):
    """手动保存知识到知识库"""
    try:
        if req.action == "create":
            result = crud_tools.create_knowledge(
                title=req.title,
                content=req.content,
                category=req.category,
                tags=req.tags,
                source="chat-extraction",
            )
        elif req.action == "update":
            if not req.target_path:
                raise HTTPException(400, "更新操作需要 target_path")
            result = crud_tools.update_knowledge(
                path=req.target_path,
                title=req.title if req.title else None,
                content=req.content,
                tags=req.tags if req.tags else None,
            )
        elif req.action == "delete":
            if not req.target_path:
                raise HTTPException(400, "删除操作需要 target_path")
            result = crud_tools.delete_knowledge(req.target_path)
        else:
            raise HTTPException(400, f"不支持的操作: {req.action}")

        if result.get("status") == "error":
            error_msg = result.get("message", "未知错误")
            if "已存在" in error_msg:
                raise HTTPException(409, error_msg)
            if "不存在" in error_msg:
                raise HTTPException(404, error_msg)
            raise HTTPException(500, error_msg)

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"操作失败: {str(e)}")


@router.post("/confirm")
async def confirm_knowledge(req: ConfirmRequest):
    """确认或取消知识库操作（Human-in-the-Loop）"""
    try:
        result = await resume_and_execute(req.thread_id, req.confirm, session_id=req.session_id)

        if req.session_id:
            status = "confirmed" if req.confirm else "rejected"
            await session_store.update_extraction_status(req.session_id, req.thread_id, status)

        return result
    except Exception as e:
        raise HTTPException(500, f"操作失败: {str(e)}")


@router.post("/sessions")
async def create_session(session_id: str = "default", name: str = "新对话"):
    await session_store.create_session(session_id, name)
    return {"id": session_id, "name": name}


@router.get("/sessions")
async def list_sessions():
    sessions = await session_store.list_sessions()
    return {"sessions": sessions}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    session = await session_store.get_session(session_id)
    if session is None:
        raise HTTPException(404, "会话不存在")
    return session


@router.delete("/sessions/{session_id}")
async def clear_session(session_id: str):
    deleted = await session_store.delete_session(session_id)
    if not deleted:
        raise HTTPException(404, "会话不存在")
    return {"status": "ok"}
