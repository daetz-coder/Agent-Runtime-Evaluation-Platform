"""
知识自动标签 — LLM 驱动的标签生成和相似度聚类。
"""

from __future__ import annotations

import json
import logging
from typing import List, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.wiki_agent.config import settings

logger = logging.getLogger(__name__)

AUTO_TAG_PROMPT = """你是一个知识库标签生成器。根据文档标题和内容，生成 3-5 个简洁的标签。

## 文档标题
{title}

## 文档内容（前 500 字）
{content_preview}

## 现有标签（尽量复用）
{existing_tags}

## 要求
1. 每个标签 2-5 个中文字或英文字
2. 优先复用已有标签
3. 标签应该描述文档的核心主题
4. 返回 JSON: {{"tags": ["标签1", "标签2", ...]}}
"""


class TagResult(BaseModel):
    tags: List[str] = Field(default_factory=list)


_auto_tag_llm: Optional[ChatOpenAI] = None


def _get_llm() -> ChatOpenAI:
    global _auto_tag_llm
    if _auto_tag_llm is None:
        _auto_tag_llm = ChatOpenAI(
            model=settings.DEEPSEEK_MODEL,
            openai_api_key=settings.DEEPSEEK_API_KEY,
            openai_api_base=settings.DEEPSEEK_BASE_URL,
            temperature=0.1,
            max_tokens=200,
        )
    return _auto_tag_llm


async def generate_tags(title: str, content: str, existing_tags: Optional[List[str]] = None) -> List[str]:
    """LLM 自动生成标签。"""
    prompt = ChatPromptTemplate.from_template(AUTO_TAG_PROMPT)

    try:
        chain = prompt | _get_llm()
        response = await chain.ainvoke({
            "title": title,
            "content_preview": content[:500] if content else "",
            "existing_tags": ", ".join(existing_tags or []),
        })

        # 解析 JSON
        text = (response.content or "").strip()
        if "{" in text:
            import re
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                data = json.loads(match.group())
                return TagResult(**data).tags
        return []

    except Exception as e:
        logger.warning("Auto-tagging failed: %s", e)
        return []
