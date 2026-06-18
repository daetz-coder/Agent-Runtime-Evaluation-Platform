"""Knowledge Agent — 知识库维护决策（create / update / delete / none）"""

from __future__ import annotations

from typing import Literal

from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.wiki_agent.agent.tools import search_tools
from app.wiki_agent.config import settings
from app.wiki_agent.wiki import service

_llm: ChatOpenAI | None = None
_structured_llm = None


def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            model=settings.DEEPSEEK_MODEL,
            api_key=settings.DEEPSEEK_API_KEY or "placeholder",
            base_url=settings.DEEPSEEK_BASE_URL,
            temperature=0.3,
        )
    return _llm


class KnowledgeDecision(BaseModel):
    """知识操作决策"""
    action: Literal["create", "update", "delete", "none"] = Field(description="操作类型")
    reason: str = Field(description="判断原因")
    path: str = Field(default="", description="知识条目路径，update/delete 时必填")
    title: str = Field(default="", description="条目标题，create 时必填")
    category: str = Field(default="", description="分类路径如 programming/python，create 时填写")
    content: str = Field(default="", description="Markdown 内容，create/update 时必填")
    tags: list[str] | None = Field(default=None, description="标签列表")

    def to_dict(self) -> dict:
        return self.model_dump()


_parser = PydanticOutputParser(pydantic_object=KnowledgeDecision)

DECIDE_PROMPT = """你是一个知识库维护决策器。根据当前对话和现有知识库，判断是否需要创建、更新、删除知识条目。

## 当前对话
用户: {user_message}
AI: {ai_response}

## 现有知识库内容
{existing_knowledge}

## 判断规则
- create：对话中包含具有长期复用价值的新知识，且现有知识库没有相关条目。必须填写 title、category 和 content。
- update：对话对现有条目进行了补充、修正或结构化完善。必须填写 path 和 content。
- delete：用户明确要求删除某个知识条目。必须填写 path。
- none：普通问答、闲聊、重复已有内容、临时性问题、没有长期保存价值。

{format_instructions}
"""

_supports_function_calling = "deepseek" in settings.DEEPSEEK_MODEL.lower()


def _get_structured_llm():
    global _structured_llm
    if _structured_llm is None and _supports_function_calling:
        _structured_llm = _get_llm().with_structured_output(KnowledgeDecision)
    return _structured_llm


def _get_related_knowledge(query: str) -> str:
    """获取与查询相关的现有知识（混合检索 + 正文预览）"""
    results = search_tools.hybrid_search(query, limit=3)
    if not results:
        return "（无相关知识）"

    entries = []
    for r in results:
        try:
            page = service.get_page(r["path"])
            preview = page.content[:500] + ("..." if len(page.content) > 500 else "")
            entries.append(f"### {r['title']} ({r['path']})\n{preview}")
        except Exception:
            entries.append(f"### {r['title']} ({r['path']})\n（读取失败）")
    return "\n\n".join(entries)


def _build_prompt(user_message: str, ai_response: str, existing_knowledge: str) -> str:
    return DECIDE_PROMPT.format(
        user_message=user_message,
        ai_response=ai_response,
        existing_knowledge=existing_knowledge,
        format_instructions=_parser.get_format_instructions(),
    )


async def decide_action(user_message: str, ai_response: str) -> KnowledgeDecision:
    """分析对话，决定是否需要对知识库进行操作"""
    existing_knowledge = _get_related_knowledge(user_message)
    prompt = _build_prompt(user_message, ai_response, existing_knowledge)

    structured = _get_structured_llm()
    if structured is not None:
        try:
            decision = await structured.ainvoke([HumanMessage(content=prompt)])
            if isinstance(decision, KnowledgeDecision) and decision.action in (
                "create",
                "update",
                "delete",
                "none",
            ):
                print(f"[Knowledge Agent] 结构化输出成功: action={decision.action}")
                return decision
            print("[Knowledge Agent] 结构化输出异常，fallback 到 PydanticOutputParser")
        except Exception as e:
            print(f"[Knowledge Agent] 结构化输出失败，fallback: {e}")

    try:
        response = await _get_llm().ainvoke([HumanMessage(content=prompt)])
        raw_text = (response.content or "").strip()
        if not raw_text:
            return KnowledgeDecision(action="none", reason="LLM 返回空内容")
        decision = _parser.parse(raw_text)
        print(f"[Knowledge Agent] PydanticOutputParser 成功: action={decision.action}")
        return decision
    except Exception as e:
        print(f"[Knowledge Agent] 决策失败: {e}")
        return KnowledgeDecision(action="none", reason=f"决策失败: {str(e)}")
