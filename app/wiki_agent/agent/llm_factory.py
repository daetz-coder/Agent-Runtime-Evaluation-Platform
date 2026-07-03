"""统一 LLM 创建工厂。

ZhipuAI 优先（如配置了 API Key），否则回退到 DeepSeek。
所有需要 LLM 的模块统一使用 create_chat_llm()，避免重复逻辑。
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

    优先使用 ZhipuAI（如配置了 ZHIPUAI_API_KEY），否则使用 DeepSeek。

    Args:
        temperature: 生成温度
        streaming: 是否启用流式输出
        max_tokens: 最大生成 token 数
    """
    if settings.ZHIPUAI_API_KEY:
        return ChatOpenAI(
            model=settings.ZHIPUAI_CHAT_MODEL,
            api_key=settings.ZHIPUAI_API_KEY,
            base_url=settings.ZHIPUAI_BASE_URL,
            temperature=temperature,
            streaming=streaming,
            max_tokens=max_tokens,
        )
    return ChatOpenAI(
        model=settings.DEEPSEEK_MODEL,
        api_key=settings.DEEPSEEK_API_KEY or "placeholder",
        base_url=settings.DEEPSEEK_BASE_URL,
        temperature=temperature,
        streaming=streaming,
        max_tokens=max_tokens,
    )
