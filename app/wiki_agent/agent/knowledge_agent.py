"""Knowledge Agent — 知识库维护决策（create / update / delete / none）"""

from __future__ import annotations

from typing import Literal

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, model_validator

from app.wiki_agent.agent.context_retriever import build_context_block, retrieve_context
from app.wiki_agent.agent.llm_factory import create_chat_llm

_llm: ChatOpenAI | None = None


def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        _llm = create_chat_llm(temperature=0.3)
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

    @model_validator(mode="after")
    def validate_action_fields(self) -> "KnowledgeDecision":
        """根据 action 类型校验必填字段"""
        missing: dict[str, dict[str, str]] = {
            "create": {
                "title": self.title,
                "category": self.category,
                "content": self.content,
            },
            "update": {"path": self.path, "content": self.content},
            "delete": {"path": self.path},
        }
        required = missing.get(self.action, {})
        empty = [k for k, v in required.items() if not v.strip()]
        if empty:
            raise ValueError(
                f"action='{self.action}' 时以下字段必填但为空: {', '.join(empty)}"
            )
        return self

    def to_dict(self) -> dict:
        return self.model_dump()


_parser = PydanticOutputParser(pydantic_object=KnowledgeDecision)

DECIDE_PROMPT = """你是一个知识库维护决策器。根据当前对话和现有知识库，判断是否需要创建、更新、删除知识条目。

## 当前对话
用户: {user_message}
AI: {ai_response}

## 已有上下文（四层记忆）
{existing_context}

## 判断规则
- create：对话中包含具有长期复用价值的新知识，且现有知识库没有相关条目。必须填写 title、category 和 content。
- update：对话对现有条目进行了补充、修正或结构化完善。必须填写 path 和 content。
- delete：用户明确要求删除某个知识条目。必须填写 path。
- none：普通问答、闲聊、重复已有内容、临时性问题、没有长期保存价值。

## Wiki 链接规则（重要）
在 content 中引用其他知识条目时，必须使用 [[页面名称]] 语法创建链接。
- 例如：相关内容参见 [[向量索引]]、[[多智能体编码工具搭建指南]]
- 链接目标应使用知识条目的标题或文件名（不含 .md 后缀）
- 如果引用现有知识库中的条目，请使用上面"已有上下文"中列出的标题

{format_instructions}
"""


def _build_prompt(user_message: str, ai_response: str, existing_context: str) -> str:
    return DECIDE_PROMPT.format(
        user_message=user_message,
        ai_response=ai_response,
        existing_context=existing_context,
        format_instructions=_parser.get_format_instructions(),
    )


async def decide_action(
    user_message: str,
    ai_response: str,
    chat_history: list[BaseMessage] | None = None,
    session_id: str | None = None,
    max_retries: int = 2,
    existing_context: str | None = None,
) -> KnowledgeDecision:
    """分析对话，决定是否需要对知识库进行操作。

    使用四层上下文（Working Memory / Session Memory / User Memory / External KB）
    检索已有知识，解析失败时将错误反馈给 LLM 重试。
    """
    # 如果没有传入已有的上下文，则重新检索（兼容旧调用）
    if existing_context is None:
        ctx = await retrieve_context(
            user_message, chat_history or [], session_id
        )
        existing_context = build_context_block(ctx) or "（无已有上下文）"

    base_prompt = _build_prompt(user_message, ai_response, existing_context)

    # DeepSeek 不支持 LangChain with_structured_output 的 json_schema response_format，
    # 统一用 PydanticOutputParser 从文本中解析 JSON。
    llm = _get_llm()
    messages = [HumanMessage(content=base_prompt)]

    for attempt in range(max_retries + 1):
        try:
            response = await llm.ainvoke(messages)
            raw_text = (response.content or "").strip()
            if not raw_text:
                return KnowledgeDecision(action="none", reason="LLM 返回空内容")
            decision = _parser.parse(raw_text)
            print(f"[Knowledge Agent] 第 {attempt + 1} 次解析成功: action={decision.action}")
            return decision
        except Exception as e:
            print(f"[Knowledge Agent] 第 {attempt + 1} 次解析失败: {e}")
            if attempt < max_retries:
                # 将校验错误反馈给 LLM，引导它修正输出
                messages.append(HumanMessage(content=(
                    f"你的回复校验失败，错误如下：\n\n{e}\n\n"
                    "请严格按照 JSON schema 重新输出，确保必填字段不为空。"
                )))
                continue

    print(f"[Knowledge Agent] 重试 {max_retries} 次后仍失败，返回 none")
    return KnowledgeDecision(action="none", reason=f"重试 {max_retries} 次后仍失败")
