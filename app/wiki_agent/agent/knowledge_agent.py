"""Knowledge Agent — 知识库维护决策（create / update / delete / none）"""

from __future__ import annotations

import json
import logging
import re
from typing import Literal

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, model_validator

from app.wiki_agent.agent.context_retriever import build_context_block, retrieve_context
from app.wiki_agent.agent.llm_factory import create_chat_llm

logger = logging.getLogger(__name__)


def _strip_output_wrapper(text: str) -> str:
    """Strip output(...) wrapper and markdown code blocks from LLM JSON.

    Handles common LLM output formats:
    - output({"action": ...})
    - ```json\n{...}\n```
    - ```\n{...}\n```
    - Raw JSON
    """
    text = text.strip()
    # Strip output({...}) wrapper
    m = re.match(r'^output\s*\((.*)\)\s*$', text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    # Strip markdown code blocks
    m = re.match(r'^```(?:json)?\s*\n?(.*?)\n?```\s*$', text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    return text


def _normalize_llm_json(data: dict) -> dict:
    """Normalize common LLM field name variations to match KnowledgeDecision schema.

    Some models return 'decision' instead of 'action', or return content as a dict.
    """
    # decision → action
    if "decision" in data and "action" not in data:
        data["action"] = data.pop("decision")
    # content as dict → JSON string
    if "content" in data and isinstance(data["content"], dict):
        lines = []
        for k, v in data["content"].items():
            lines.append(f"### {k}\n{v}" if isinstance(v, str) else f"### {k}\n{json.dumps(v, ensure_ascii=False)}")
        data["content"] = "\n\n".join(lines)
    # Ensure reason exists
    if "reason" not in data:
        data["reason"] = ""
    return data

_llm: ChatOpenAI | None = None
_structured_llm: ChatOpenAI | None = None


def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        _llm = create_chat_llm(temperature=0.3)
    return _llm


def _get_structured_llm():
    """获取支持 with_structured_output 的 LLM（如果可用）。

    使用 include_raw=True 以便在解析失败时可以从 raw 中提取原始文本，
    处理模型输出 output({...}) 包装的情况。
    """
    global _structured_llm
    if _structured_llm is None:
        try:
            llm = _get_llm()
            _structured_llm = llm.with_structured_output(KnowledgeDecision, include_raw=True)
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

# 尝试从 YAML 加载 Prompt，失败则使用硬编码 fallback
try:
    from prompts import get_prompt
    DECIDE_PROMPT = get_prompt("wiki_agent/decide")
except Exception:
    DECIDE_PROMPT = """你是一个知识库维护决策器。根据当前对话和现有知识库，判断是否需要创建、更新、删除知识条目。

## 当前对话
用户: {user_message}
AI: {ai_response}

## 已有上下文（四层记忆）
{existing_context}

## 判断规则
- create：对话中包含可复用的知识（技术方案、配置方法、操作步骤、经验总结、概念解释等），且现有知识库没有相关条目。必须填写 title、category 和 content。
- update：对话对现有条目进行了补充、修正或结构化完善。必须填写 path 和 content。
- delete：用户明确要求删除某个知识条目。必须填写 path。
- none：仅限于纯闲聊、打招呼、或完全重复已有内容的对话。注意：解释概念、总结信息、回答技术问题等都可能包含可复用知识，倾向于 create 而非 none。

## 倾向 create 的信号
- 用户询问某个技术概念或工具的用法
- AI 给出了结构化的解释或步骤
- 对话涉及配置、命令、代码片段
- 信息具有跨会话的参考价值

## Wiki 链接规则（重要）
在 content 中引用其他知识条目时，必须使用 [[页面名称]] 语法创建链接。
- 例如：相关内容参见 [[向量索引]]、[[多智能体编码工具搭建指南]]
- 链接目标应使用知识条目的标题或文件名（不含 .md 后缀）
- 如果引用现有知识库中的条目，请使用上面"已有上下文"中列出的标题

请直接返回 JSON 格式的决策结果，不要添加 output() 包装。
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

            # include_raw=True 返回 {"raw": msg, "parsed": obj|None, "parsing_error": err|None}
            if isinstance(result, dict) and "parsed" in result:
                parsed = result["parsed"]
                if parsed is not None and isinstance(parsed, KnowledgeDecision):
                    print(f"[Knowledge Agent] structured_output 第 {attempt + 1} 次成功: action={parsed.action}")
                    return parsed
                # parsed 为 None — 尝试从 raw 中手动解析
                raw_msg = result.get("raw")
                raw_text = raw_msg.content if hasattr(raw_msg, "content") else str(raw_msg)
                stripped = _strip_output_wrapper(raw_text)
                try:
                    data = json.loads(stripped)
                    data = _normalize_llm_json(data)
                    decision = KnowledgeDecision.model_validate(data)
                    print(f"[Knowledge Agent] structured_output 第 {attempt + 1} 次从 raw 手动解析成功: action={decision.action}")
                    return decision
                except Exception as inner_e:
                    last_error = f"parsed=None, raw 手动解析也失败: {inner_e}"
                    logger.warning("structured_output attempt %d/%d: %s", attempt + 1, max_retries + 1, last_error)
                    continue

            # 兼容不带 include_raw 的情况
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
            raw_text = _strip_output_wrapper(raw_text)
            # Extract JSON, normalize field names, then validate
            try:
                # Try to find JSON in the text (handles markdown code blocks etc.)
                json_match = re.search(r'\{[\s\S]*\}', raw_text)
                if json_match:
                    data = json.loads(json_match.group())
                    data = _normalize_llm_json(data)
                    decision = KnowledgeDecision.model_validate(data)
                else:
                    decision = _parser.parse(raw_text)
            except (json.JSONDecodeError, Exception):
                # Fallback to standard parser
                decision = _parser.parse(raw_text)
            print(f"[Knowledge Agent] parser 第 {attempt + 1} 次解析成功: action={decision.action}")
            return decision
        except Exception as e:
            print(f"[Knowledge Agent] parser 第 {attempt + 1} 次解析失败: {e}")
            if attempt < max_retries:
                messages.append(HumanMessage(content=(
                    f"你的回复校验失败，错误如下：\n\n{e}\n\n"
                    "请严格按照以下 JSON schema 重新输出，确保必填字段不为空：\n"
                    '{"action": "create|update|delete|none", "reason": "原因", '
                    '"path": "", "title": "", "category": "", "content": "字符串", "tags": []}\n'
                    "注意：content 必须是字符串类型，不能是对象。"
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
