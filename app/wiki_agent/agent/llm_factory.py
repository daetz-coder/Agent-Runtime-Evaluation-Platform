"""Wiki Agent 统一 LLM 创建工厂。

优先 DeepSeek（与平台默认一致），未配置时回退 ZhipuAI。
专为 wiki_agent 流式输出 / max_tokens 需求定制；评估侧 Judge LLM
由 app.evaluators.base.BaseEvaluator 自行创建，路径独立。
"""

from __future__ import annotations

from langchain_openai import ChatOpenAI

from app.wiki_agent.config import settings


def create_chat_llm(
    temperature: float = 0.7,
    streaming: bool = False,
    max_tokens: int | None = None,
) -> ChatOpenAI:
    """创建 ChatOpenAI 实例。

    优先使用 DeepSeek（如配置了 DEEPSEEK_API_KEY），否则使用 ZhipuAI。

    Args:
        temperature: 生成温度
        streaming: 是否启用流式输出
        max_tokens: 最大生成 token 数
    """
    if settings.DEEPSEEK_API_KEY:
        return ChatOpenAI(
            model=settings.DEEPSEEK_MODEL,
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            temperature=temperature,
            streaming=streaming,
            max_tokens=max_tokens,
        )
    return ChatOpenAI(
        model=settings.ZHIPUAI_CHAT_MODEL,
        api_key=settings.ZHIPUAI_API_KEY or "placeholder",
        base_url=settings.ZHIPUAI_BASE_URL,
        temperature=temperature,
        streaming=streaming,
        max_tokens=max_tokens,
    )
