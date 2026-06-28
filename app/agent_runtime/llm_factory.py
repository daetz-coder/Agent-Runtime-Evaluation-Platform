"""
llm_factory — create LLM instances based on provider/model configuration.

Reuses the platform's existing LLM provider setup (OpenAI, Anthropic, DeepSeek, GLM, Qwen).
"""

from __future__ import annotations

import logging
from typing import Optional

from langchain_core.language_models import BaseChatModel

from app.core.config import settings

logger = logging.getLogger(__name__)


def create_llm(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.0,
) -> BaseChatModel:
    """
    Create an LLM instance based on the specified provider and model.

    Args:
        provider: LLM provider name (deepseek, openai, anthropic, zhipuai, qwen).
                  Defaults to settings.DEFAULT_LLM_PROVIDER.
        model: Model name. Defaults to the provider's default model.
        temperature: Sampling temperature.

    Returns:
        A LangChain-compatible chat model instance.

    Raises:
        ValueError: If the provider is not supported or API key is missing.
    """
    provider = (provider or settings.DEFAULT_LLM_PROVIDER).lower()

    if provider == "openai":
        return _create_openai(model or "gpt-4o-mini", temperature)
    elif provider == "anthropic":
        return _create_anthropic(model or "claude-sonnet-4-20250514", temperature)
    elif provider == "deepseek":
        return _create_deepseek(model or settings.DEEPSEEK_MODEL, temperature)
    elif provider in ("zhipuai", "glm"):
        return _create_zhipuai(model or settings.ZHIPUAI_MODEL, temperature)
    elif provider == "qwen":
        return _create_qwen(model or settings.QWEN_MODEL, temperature)
    else:
        raise ValueError(
            f"Unsupported LLM provider: '{provider}'. "
            f"Supported: openai, anthropic, deepseek, zhipuai, qwen"
        )


def _create_openai(model: str, temperature: float) -> BaseChatModel:
    if not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not configured")
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=settings.OPENAI_API_KEY,
    )


def _create_anthropic(model: str, temperature: float) -> BaseChatModel:
    if not settings.ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY is not configured")
    from langchain_anthropic import ChatAnthropic
    return ChatAnthropic(
        model=model,
        temperature=temperature,
        api_key=settings.ANTHROPIC_API_KEY,
    )


def _create_deepseek(model: str, temperature: float) -> BaseChatModel:
    if not settings.DEEPSEEK_API_KEY:
        raise ValueError("DEEPSEEK_API_KEY is not configured")
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
    )


def _create_zhipuai(model: str, temperature: float) -> BaseChatModel:
    if not settings.ZHIPUAI_API_KEY:
        raise ValueError("ZHIPUAI_API_KEY is not configured")
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=settings.ZHIPUAI_API_KEY,
        base_url="https://open.bigmodel.cn/api/paas/v4",
    )


def _create_qwen(model: str, temperature: float) -> BaseChatModel:
    if not settings.QWEN_API_KEY:
        raise ValueError("QWEN_API_KEY is not configured")
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=settings.QWEN_API_KEY,
        base_url=settings.QWEN_BASE_URL,
    )
