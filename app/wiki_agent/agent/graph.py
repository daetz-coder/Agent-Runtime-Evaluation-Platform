"""Wiki Agent — LangGraph 编排（search → respond → decide → execute）

纯业务逻辑，不包含任何评估代码。评估由 eval_middleware + SDK 自动采集。
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncGenerator
from typing import Any, Literal, TypedDict

import aiosqlite
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field

from app.wiki_agent.agent import knowledge_agent
from app.wiki_agent.agent.context_retriever import RetrievedContext, build_context_block, build_context_block_from_dict, retrieve_context
from app.wiki_agent.agent.eval_middleware import (
    finish_session,
    instrument_graph,
    record_retrieval,
    start_session,
    update_context,
    wrap_llm,
)
from app.wiki_agent.agent.tools import crud_tools
from app.wiki_agent.config import settings
from app.wiki_agent.session import store as session_store

_CHECKPOINT_DB = os.path.join(os.path.dirname(settings.DB_PATH), "checkpoints.db")
os.makedirs(os.path.dirname(_CHECKPOINT_DB), exist_ok=True)

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

# 创建 LLM 并用 SDK 包裹（自动采集 LLM 调用）
# 优先使用 ZhipuAI（如配置了 API Key），否则回退到 DeepSeek
_chat_llm_model = settings.ZHIPUAI_CHAT_MODEL if settings.ZHIPUAI_API_KEY else settings.DEEPSEEK_MODEL
_chat_llm_key = settings.ZHIPUAI_API_KEY or settings.DEEPSEEK_API_KEY
_chat_llm_base = settings.ZHIPUAI_BASE_URL if settings.ZHIPUAI_API_KEY else settings.DEEPSEEK_BASE_URL

chat_llm = wrap_llm(
    ChatOpenAI(
        model=_chat_llm_model,
        api_key=_chat_llm_key,
        base_url=_chat_llm_base,
        temperature=0.7,
        # streaming=True 让 astream() 真正逐 token 流式输出。
        # ainvoke() 不受影响，始终走非流式路径。
        streaming=True,
    )
)


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


# ── key_facts 提取（业务逻辑，非评估） ────────────────────────


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
    # 跳过简单查询，不提取事实
    simple_patterns = [
        r'^(你好|hi|hello|hey|嗨|您好)',
        r'^(你是谁|你叫什么|who are you)',
        r'^(什么是|怎么用|如何|解释|说明)',
        r'^(谢谢|感谢|thanks)',
        r'^(再见|bye|拜拜)',
    ]
    import re
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
        # 并行读取用户记忆和会话记忆
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

        # 复用模块级 LLM 实例，避免每次创建新连接
        _fact_llm = chat_llm.__class__(
            model=_chat_llm_model,
            api_key=_chat_llm_key,
            base_url=_chat_llm_base,
            temperature=0,
            max_tokens=400,
        )

        # 先尝试 with_structured_output（支持 Function Calling 的 LLM）
        # 失败则降级到 PydanticOutputParser（DeepSeek 等返回 code fence 的 LLM）
        try:
            structured_llm = _fact_llm.with_structured_output(FactExtractionResult)
            result: FactExtractionResult = await structured_llm.ainvoke([HM(content=prompt)])
        except Exception:
            # 降级：调用普通 LLM，从 code fence 中提取 JSON
            response = await _fact_llm.ainvoke([HM(content=prompt)])
            content = response.content or ""
            import re
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


# ── 节点（纯业务逻辑） ──────────────────────────────────────


async def search(state: WikiState, config: RunnableConfig) -> WikiState:
    """统一检索四路记忆（KB + user_memory + session_memory + history）"""
    print("[Wiki Agent] 检索上下文...")
    user_message = state["user_message"]
    configurable = _get_configurable(config)
    chat_history: list[BaseMessage] = configurable.get("chat_history") or []
    session_id = configurable.get("session_id")
    started = asyncio.get_running_loop().time()

    # 统一检索
    ctx = await retrieve_context(user_message, chat_history, session_id)
    duration_ms = round((asyncio.get_running_loop().time() - started) * 1000, 2)

    # 记录检索事件（SDK 无法自动采集检索细节）
    record_retrieval(user_message, ctx.wiki_results, duration_ms)

    # wiki_text 向后兼容
    wiki_text = None
    if ctx.wiki_results:
        lines = [f"- {r['title']} ({r['path']}): {r['snippet']}" for r in ctx.wiki_results[:3]]
        wiki_text = "\n".join(lines)

    # 提取结构化 key_facts，按 scope 分流
    session_facts_raw, user_facts_raw = await _extract_key_facts(
        user_message, ctx.wiki_results, chat_history, session_id
    )

    # 异步存储记忆（不阻塞主流程）
    async def _store_memories():
        try:
            # Session Memory: 合并到当前 session
            if session_id and session_facts_raw:
                all_session_facts = await session_store.merge_session_key_facts(session_id, session_facts_raw)
                ctx.session_facts = all_session_facts
                print(f"[Session Memory] 新增 {len(session_facts_raw)} 条，累积 {len(all_session_facts)} 条")

            # User Memory: 合并到用户级持久记忆
            if user_facts_raw:
                all_user_facts = await session_store.merge_user_memory(user_facts_raw)
                ctx.user_facts = all_user_facts
                print(f"[User Memory] 新增 {len(user_facts_raw)} 条，累积 {len(all_user_facts)} 条")
        except Exception as e:
            print(f"[Memory] 异步存储失败: {e}")

    asyncio.create_task(_store_memories())

    update_context({"key_facts": ctx.session_facts, "user_facts": ctx.user_facts})

    # 日志
    context_block = build_context_block(ctx)
    print(
        f"[Context] wiki: {len(ctx.wiki_results)} docs, "
        f"user: {len(ctx.user_facts)} facts, "
        f"session: {len(ctx.session_facts)} facts, "
        f"history: {len(ctx.history_summary)} chars → {len(context_block)} chars"
    )

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
    }


async def respond(state: WikiState, config: RunnableConfig) -> WikiState:
    """流式或非流式生成回复"""
    print("[Wiki Agent] 生成回复...")
    configurable = _get_configurable(config)
    queue: asyncio.Queue | None = configurable.get("event_queue")
    chat_history: list[BaseMessage] = configurable.get("chat_history") or []

    wiki_text = state.get("wiki_text")
    if wiki_text:
        await _emit(queue, {"type": "wiki_results", "results": wiki_text})

    messages = _build_llm_messages(state, chat_history)
    collected = ""

    # 始终走 astream — 有 event_queue 时逐 token 推 SSE，无 queue 时在本地聚合
    async for chunk in chat_llm.astream(messages):
        text = _chunk_text(chunk)
        if not text:
            continue
        collected += text
        if queue is not None:
            await _emit(queue, {"type": "content", "text": text})

    return {**state, "ai_response": collected, "stage": "respond"}


async def decide(state: WikiState, config: RunnableConfig) -> WikiState:
    """分析对话，决定知识库操作"""
    print("[Wiki Agent] 分析对话...")
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

    # 复用 search 阶段已检索的上下文，避免重复检索
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

    return {**state, "decision": decision_dict, "stage": "decide"}


async def execute(state: WikiState, config: RunnableConfig) -> WikiState:
    """Human-in-the-Loop：等待用户确认后执行 CRUD"""
    user_confirmed = interrupt({})

    if not user_confirmed:
        print("[Wiki Agent] 用户取消操作")
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
    """创建 wiki agent graph（用 SDK 自动采集包裹）"""
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
    return instrument_graph(compiled)


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

    eval_task_id = await start_session(
        user_message,
        session_id,
        "stream",
        thread_id=thread_id,
        history_count=len(chat_history),
    )

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

    async def _run_graph():
        try:
            await queue.put({"type": "evaluation_task", "task_id": eval_task_id})
            result = await graph.ainvoke(initial_state, config)
            extraction = _extraction_from_result(result, thread_id)
            if extraction:
                await queue.put({"type": "extraction", "data": extraction})
            await finish_session(auto_run=True)
            await queue.put({"type": "_done", "result": result})
        except Exception as e:
            await finish_session(auto_run=False)
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

    eval_task_id = await start_session(
        user_message,
        session_id,
        "invoke",
        thread_id=thread_id,
        history_count=len(chat_history),
    )

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
        await finish_session(auto_run=False)
        raise
    await finish_session(auto_run=True)
    return {
        "content": result.get("ai_response", ""),
        "wiki_text": result.get("wiki_text"),
        "extraction": _extraction_from_result(result, thread_id),
        "evaluation_task_id": eval_task_id,
    }


async def resume_and_execute(
    thread_id: str,
    confirm: bool,
    *,
    session_id: str | None = None,
) -> dict:
    """从 checkpoint 恢复，执行或取消知识库操作"""
    graph = await get_wiki_graph()

    # 确认/取消时复用当前会话的评估任务，避免每次操作再创建一条重复 task
    eval_task_id: str | None = None
    if session_id:
        eval_task_id = await session_store.get_active_eval_task_id(session_id)

    if not eval_task_id:
        eval_task_id = await start_session(
            f"{'Confirm' if confirm else 'Cancel'} pending wiki knowledge-base action",
            session_id,
            "resume",
            thread_id=thread_id,
            confirm=confirm,
        )
    else:
        try:
            from sdk import get_collector
            from sdk.collector import ActionType

            collector = get_collector()
            collector.attach(eval_task_id)
            collector.record(
                ActionType.THINK,
                {
                    "thought": f"{'Confirm' if confirm else 'Cancel'} pending wiki knowledge-base action",
                    "thread_id": thread_id,
                },
            )
        except ImportError:
            pass  # SDK not available — skip eval recording

    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

    try:
        result = await graph.ainvoke(Command(resume=confirm), config)
    except Exception:
        await finish_session(auto_run=False)
        raise
    await finish_session(auto_run=True)

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
