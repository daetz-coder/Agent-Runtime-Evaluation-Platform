"""
多评估器共识引擎 — 多个 LLM 独立评分，输出均值和方差。

支持 DeepSeek / OpenAI / Anthropic 三模型共识。
如果某个模型的 API key 未配置，自动跳过。

使用方式：
    from app.evaluators.consensus import ConsensusEvaluator
    evaluator = ConsensusEvaluator()
    result = await evaluator.evaluate(goal="...", trajectory=[...])
    # result.mean_score, result.std_score, result.individual_scores
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.core.config import settings
from app.models.schemas import TrajectoryStep

logger = logging.getLogger(__name__)


class ConsensusResult(BaseModel):
    """多模型共识评估结果。"""
    mean_score: float = Field(description="多模型均分")
    std_score: float = Field(description="标准差（越小=一致性越高=越可信）")
    model_count: int = Field(description="参与评估的模型数")
    individual_scores: Dict[str, float] = Field(default_factory=dict)
    dimension: str = Field(default="planning")
    consensus_type: str = Field(
        default="same_provider_multi_model",
        description="共识类型: cross_provider(跨厂商) / same_provider_multi_model(同厂商多模型) / temperature_diversity(温度多样性)"
    )


def _consensus_type(providers: list) -> str:
    """判断共识类型。"""
    names = [p[0] for p in providers]
    unique_vendors = set()
    for n in names:
        if n.startswith("deepseek"):
            unique_vendors.add("deepseek")
        elif n.startswith("openai"):
            unique_vendors.add("openai")
        elif n.startswith("anthropic"):
            unique_vendors.add("anthropic")
        elif n.startswith("glm"):
            unique_vendors.add("zhipuai")
        elif n.startswith("qwen"):
            unique_vendors.add("qwen")
    if len(unique_vendors) >= 2:
        return "cross_provider"
    if any("t0." in n for n in names):
        return "temperature_diversity"
    return "same_provider_multi_model"


class ConsensusEvaluator:
    """多模型共识评估器。

    对同一 trajectory 使用多个 LLM 独立评分，输出均值和标准差。
    标准差越小 = 评估一致性越高 = 评分越可信。
    """

    def __init__(self):
        self._providers = self._build_providers()

    def _build_providers(self) -> List[tuple[str, Any]]:
        """构建可用 LLM 提供者列表。

        优先级：
        1. 跨厂商共识（DeepSeek + OpenAI + Anthropic）— 最可靠
        2. 同厂商多模型共识（deepseek-chat + deepseek-reasoner）— 仅需 DeepSeek API
        3. 温度多样性共识（同模型不同 temperature）— 兜底方案
        """
        from langchain_openai import ChatOpenAI
        from langchain_anthropic import ChatAnthropic

        providers = []

        # DeepSeek — 多个模型变体
        if settings.DEEPSEEK_API_KEY:
            providers.append((
                "deepseek-chat",
                ChatOpenAI(
                    model="deepseek-chat",
                    openai_api_key=settings.DEEPSEEK_API_KEY,
                    openai_api_base=settings.DEEPSEEK_BASE_URL,
                    temperature=0,
                ),
            ))

        # GLM (ZhipuAI)
        if settings.ZHIPUAI_API_KEY:
            try:
                from langchain_community.chat_models import ChatZhipuAI
                providers.append((
                    "glm-4",
                    ChatZhipuAI(
                        model=settings.ZHIPUAI_MODEL,
                        api_key=settings.ZHIPUAI_API_KEY,
                        temperature=0,
                    ),
                ))
            except ImportError:
                logger.warning("langchain_community not installed — skipping GLM provider")

        # Qwen (DashScope) — OpenAI 兼容 API
        if settings.QWEN_API_KEY:
            providers.append((
                "qwen-plus",
                ChatOpenAI(
                    model=settings.QWEN_MODEL,
                    openai_api_key=settings.QWEN_API_KEY,
                    openai_api_base=settings.QWEN_BASE_URL,
                    temperature=0,
                ),
            ))
            # DeepSeek Reasoner（同 API key，不同模型）
            providers.append((
                "deepseek-reasoner",
                ChatOpenAI(
                    model="deepseek-reasoner",
                    openai_api_key=settings.DEEPSEEK_API_KEY,
                    openai_api_base=settings.DEEPSEEK_BASE_URL,
                    temperature=0,
                ),
            ))

        # OpenAI（跨厂商）
        if settings.OPENAI_API_KEY:
            providers.append((
                "openai",
                ChatOpenAI(
                    model=settings.DEFAULT_LLM_MODEL,
                    openai_api_key=settings.OPENAI_API_KEY,
                    temperature=0,
                ),
            ))

        # Anthropic（跨厂商）
        if settings.ANTHROPIC_API_KEY:
            providers.append((
                "anthropic",
                ChatAnthropic(
                    model=settings.DEFAULT_LLM_MODEL,
                    anthropic_api_key=settings.ANTHROPIC_API_KEY,
                    temperature=0,
                ),
            ))

        # 兜底：如果只有 1 个提供者（极端情况），加 temperature 变体
        if len(providers) == 1:
            name, llm = providers[0]
            providers.append((
                f"{name}-t0.7",
                ChatOpenAI(
                    model=settings.DEEPSEEK_MODEL,
                    openai_api_key=settings.DEEPSEEK_API_KEY,
                    openai_api_base=settings.DEEPSEEK_BASE_URL,
                    temperature=0.7,
                ),
            ))

        return providers

    @property
    def available_providers(self) -> List[str]:
        return [p[0] for p in self._providers]

    async def evaluate(
        self,
        goal: str,
        trajectory: List[TrajectoryStep],
        context: Optional[Dict[str, Any]] = None,
        dimension: str = "planning",
    ) -> ConsensusResult:
        """多模型共识评估。

        Args:
            goal: Agent 任务目标
            trajectory: 执行轨迹
            context: 附加上下文
            dimension: 评估维度（planning/tactical/tool_use/memory/replan）
        """
        from app.evaluators import (
            PlanningEvaluator, TacticalEvaluator,
            ToolUseEvaluator, MemoryEvaluator, ReplanEvaluator,
        )

        evaluator_class = {
            "planning": PlanningEvaluator,
            "tactical": TacticalEvaluator,
            "tool_use": ToolUseEvaluator,
            "memory": MemoryEvaluator,
            "replan": ReplanEvaluator,
        }.get(dimension, PlanningEvaluator)

        async def score_with_provider(name: str, llm) -> float:
            try:
                ev = evaluator_class(llm=llm)
                result = await ev.evaluate(goal=goal, trajectory=trajectory, context=context)
                score = getattr(result, "overall", 0)
                logger.info(f"Consensus [{name}]: {score:.1f}")
                return score
            except Exception as e:
                logger.warning(f"Consensus [{name}] failed: {e}")
                return None

        # 并行执行所有提供者
        tasks = [score_with_provider(name, llm) for name, llm in self._providers]
        scores_list = await asyncio.gather(*tasks)

        # 过滤失败的结果
        individual = {}
        valid_scores = []
        for (name, _), score in zip(self._providers, scores_list):
            if score is not None:
                individual[name] = round(score, 1)
                valid_scores.append(score)

        if not valid_scores:
            return ConsensusResult(
                mean_score=0, std_score=0, model_count=0,
                individual_scores={}, dimension=dimension,
                consensus_type=_consensus_type(self._providers),
            )

        n = len(valid_scores)
        mean = sum(valid_scores) / n
        variance = sum((s - mean) ** 2 for s in valid_scores) / n
        std = variance ** 0.5

        return ConsensusResult(
            mean_score=round(mean, 1),
            std_score=round(std, 2),
            model_count=n,
            individual_scores=individual,
            dimension=dimension,
            consensus_type=_consensus_type(self._providers),
        )

    async def evaluate_all_dimensions(
        self,
        goal: str,
        trajectory: List[TrajectoryStep],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, ConsensusResult]:
        """对所有 6 个维度进行共识评估。"""
        dimensions = ["planning", "tactical", "tool_use", "memory", "replan", "retrieval"]
        tasks = [
            self.evaluate(goal, trajectory, context, dim)
            for dim in dimensions
        ]
        results = await asyncio.gather(*tasks)
        return dict(zip(dimensions, results))
