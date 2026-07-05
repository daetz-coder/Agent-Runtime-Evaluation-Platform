"""Knowledge Agent — 知识库维护决策（create / update / delete / none）"""

from __future__ import annotations

import logging
from typing import Literal

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, model_validator

from app.wiki_agent.agent.context_retriever import build_context_block, retrieve_context
from app.wiki_agent.agent.llm_factory import create_chat_llm

logger = logging.getLogger(__name__)

_llm: ChatOpenAI | None = None
_structured_llm: ChatOpenAI | None = None


def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        _llm = create_chat_llm(temperature=0.3)
    return _llm


def _get_structured_llm() -> ChatOpenAI | None:
    """获取支持 with_structured_output 的 LLM（如果可用）。"""
    global _structured_llm
    if _structured_llm is None:
        try:
            llm = _get_llm()
            _structured_llm = llm.with_structured_output(KnowledgeDecision)
        except Exception as e:
            logger.warning("with_structured_output not available: %s, falling back to PydanticOutputParser", e)
            _structured_llm = False  # 标记为不可用，避免重复尝试
    return _structured_llm if _structured_llm is not False else None


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

请直接调用 output 函数返回决策结果。
"""


async def decide_action(
    user_message: str,
    ai_response: str,
    chat_history: list[BaseMessage] | None = None,
    session_id: str | None = None,
    max_retries: int = 2,
    existing_context: str | None = None,
) -> KnowledgeDecision:
    """分析对话，决定是否需要对知识库进行操作。

    优先使用 with_structured_output（API 层 schema 约束），
    不可用时回退到 PydanticOutputParser（文本解析 + 重试）。
    """
    # 如果没有传入已有的上下文，则重新检索（兼容旧调用）
    if existing_context is None:
        ctx = await retrieve_context(
            user_message, chat_history or [], session_id
        )
        existing_context = build_context_block(ctx) or "（无已有上下文）"

    # ── 路径 1：with_structured_output（推荐） ──
    structured_llm = _get_structured_llm()
    if structured_llm is not None:
        return await _decide_with_structured_output(
            user_message, ai_response, existing_context, structured_llm, max_retries
        )

    # ── 路径 2：PydanticOutputParser（回退） ──
    return await _decide_with_parser(
        user_message, ai_response, existing_context, max_retries
    )


async def _decide_with_structured_output(
    user_message: str,
    ai_response: str,
    existing_context: str,
    structured_llm,
    max_retries: int,
) -> KnowledgeDecision:
    """使用 with_structured_output 决策（API 层 schema 约束 + 自动重试）。"""
    prompt = ChatPromptTemplate.from_template(DECIDE_PROMPT)
    chain = prompt | structured_llm

    inputs = {
        "user_message": user_message,
        "ai_response": ai_response,
        "existing_context": existing_context,
    }

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            retry_inputs = dict(inputs)
            if attempt > 0 and last_error:
                # 把错误反馈给 LLM
                retry_inputs["existing_context"] = (
                    f"{existing_context}\n\n⚠️ 上一次输出校验失败: {last_error}\n"
                    f"请确保 action='{_guess_action(user_message)}' 时必填字段不为空。"
                )

            result = await chain.ainvoke(retry_inputs)

            if isinstance(result, KnowledgeDecision):
                print(f"[Knowledge Agent] structured_output 第 {attempt + 1} 次成功: action={result.action}")
                return result

            if isinstance(result, dict):
                decision = KnowledgeDecision.model_validate(result)
                print(f"[Knowledge Agent] structured_output 第 {attempt + 1} 次成功: action={decision.action}")
                return decision

            last_error = f"Expected KnowledgeDecision, got {type(result).__name__}"

        except Exception as e:
            last_error = str(e)
            logger.warning("structured_output attempt %d/%d failed: %s", attempt + 1, max_retries + 1, last_error)

    # 全部失败 → 回退到 parser
    logger.warning("structured_output failed after %d retries, falling back to parser", max_retries + 1)
    return await _decide_with_parser(user_message, ai_response, existing_context, max_retries)


async def _decide_with_parser(
    user_message: str,
    ai_response: str,
    existing_context: str,
    max_retries: int,
) -> KnowledgeDecision:
    """使用 PydanticOutputParser 决策（文本解析 + 重试）。"""
    base_prompt = DECIDE_PROMPT.format(
        user_message=user_message,
        ai_response=ai_response,
        existing_context=existing_context,
    )

    llm = _get_llm()
    messages = [HumanMessage(content=base_prompt)]

    for attempt in range(max_retries + 1):
        try:
            response = await llm.ainvoke(messages)
            raw_text = (response.content or "").strip()
            if not raw_text:
                return KnowledgeDecision(action="none", reason="LLM 返回空内容")
            decision = _parser.parse(raw_text)
            print(f"[Knowledge Agent] parser 第 {attempt + 1} 次解析成功: action={decision.action}")
            return decision
        except Exception as e:
            print(f"[Knowledge Agent] parser 第 {attempt + 1} 次解析失败: {e}")
            if attempt < max_retries:
                messages.append(HumanMessage(content=(
                    f"你的回复校验失败，错误如下：\n\n{e}\n\n"
                    "请严格按照 JSON schema 重新输出，确保必填字段不为空。"
                )))
                continue

    print(f"[Knowledge Agent] 重试 {max_retries} 次后仍失败，返回 none")
    return KnowledgeDecision(action="none", reason=f"重试 {max_retries} 次后仍失败")


def _guess_action(user_message: str) -> str:
    """从用户消息猜测最可能的 action（用于错误反馈）。"""
    msg = user_message.lower()
    if any(w in msg for w in ["创建", "新建", "添加", "记录", "保存"]):
        return "create"
    if any(w in msg for w in ["更新", "修改", "补充", "完善"]):
        return "update"
    if any(w in msg for w in ["删除", "移除"]):
        return "delete"
    return "none"
