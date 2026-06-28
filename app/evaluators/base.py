"""
Base evaluator class for all evaluation dimensions.

支持的 action_type：
- plan / plan_update       — 规划输出
- tool_call / tool_result  — 工具调用与返回
- memory_write / memory_read — 记忆读写
- state_change             — 状态变化
- think / replan           — 思考与重规划
- failure                  — 失败/异常
- node_execute / tool_decision — 节点执行与工具决策
"""

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.evaluators.trajectory_compressor import TrajectoryCompressor
from app.models.action_types import ActionType
from app.models.schemas import TrajectoryStep

logger = logging.getLogger(__name__)


class BaseEvaluator(ABC):
    """Base class for all evaluators."""

    def __init__(self, llm: Optional[BaseChatModel] = None):
        """Initialize evaluator with optional LLM override."""
        self.llm = llm or self._get_default_llm()
        # Store raw judge data for the transparency panel
        self._last_judge_raw: Optional[Dict[str, Any]] = None
        self._judge_raw_history: List[Dict[str, Any]] = []

    def get_last_judge_raw(self) -> Optional[Dict[str, Any]]:
        """Return raw judge prompt/response from the most recent LLM call."""
        return self._last_judge_raw

    def get_judge_raw_history(self) -> List[Dict[str, Any]]:
        """Return all judge raw entries from this evaluation."""
        return list(self._judge_raw_history)

    def _get_default_llm(self) -> BaseChatModel:
        """Get default LLM based on configuration."""
        provider = settings.DEFAULT_LLM_PROVIDER.lower()

        if provider == "anthropic":
            return ChatAnthropic(
                model=settings.DEFAULT_LLM_MODEL,
                anthropic_api_key=settings.ANTHROPIC_API_KEY,
                temperature=0,
            )
        elif provider == "deepseek":
            return ChatOpenAI(
                model=settings.DEEPSEEK_MODEL,
                openai_api_key=settings.DEEPSEEK_API_KEY,
                openai_api_base=settings.DEEPSEEK_BASE_URL,
                temperature=0,
            )
        elif provider == "glm":
            from langchain_community.chat_models import ChatZhipuAI

            return ChatZhipuAI(
                model=settings.ZHIPUAI_MODEL,
                api_key=settings.ZHIPUAI_API_KEY,
                temperature=0,
            )
        elif provider == "qwen":
            # Qwen DashScope is OpenAI-compatible
            return ChatOpenAI(
                model=settings.QWEN_MODEL,
                openai_api_key=settings.QWEN_API_KEY,
                openai_api_base=settings.QWEN_BASE_URL,
                temperature=0,
            )
        else:  # openai
            return ChatOpenAI(
                model=settings.DEFAULT_LLM_MODEL,
                openai_api_key=settings.OPENAI_API_KEY,
                temperature=0,
            )

    @abstractmethod
    async def evaluate(
        self,
        goal: str,
        trajectory: List[TrajectoryStep],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate agent behavior.

        Args:
            goal: The original goal/objective
            trajectory: List of agent execution steps
            context: Additional context for evaluation

        Returns:
            Dictionary containing scores and feedback
        """
        pass

    def _format_trajectory(
        self,
        trajectory: List[TrajectoryStep],
        compress: bool = True,
    ) -> str:
        """Format trajectory steps into readable text.

        Args:
            trajectory: List of trajectory steps.
            compress: If True (default), run through the 4-stage compression
                      pipeline. Set to False to get raw full-concatenation output.
        """
        if compress:
            compressor = TrajectoryCompressor()
            return compressor.compress(trajectory)
        return self._format_trajectory_raw(trajectory)

    @staticmethod
    def _format_trajectory_raw(trajectory: List[TrajectoryStep]) -> str:
        """Full concatenation — no compression (opt-out fallback)."""
        lines = []
        for step in trajectory:
            lines.append(f"Step {step.step_number} [{step.action_type}]:")
            lines.append(f"  Action: {step.action_detail}")
            if step.observation:
                lines.append(f"  Observation: {step.observation}")
            lines.append("")
        return "\n".join(lines)

    def _extract_plans(self, trajectory: List[TrajectoryStep]) -> List[Dict[str, Any]]:
        """Extract planning steps from trajectory."""
        return [step.action_detail for step in trajectory if step.action_type == "plan"]

    def _extract_tool_calls(self, trajectory: List[TrajectoryStep]) -> List[Dict[str, Any]]:
        """Extract tool call steps from trajectory."""
        return [
            {
                "step": step.step_number,
                "tool": step.action_detail.get("tool_name"),
                "input": step.action_detail.get("input"),
                "output": step.observation,
            }
            for step in trajectory
            if step.action_type == "tool_call"
        ]

    def _extract_replans(self, trajectory: List[TrajectoryStep]) -> List[Dict[str, Any]]:
        """Extract replanning events from trajectory."""
        return [
            {
                "step": step.step_number,
                "reason": step.action_detail.get("reason"),
                "new_plan": step.action_detail.get("new_plan"),
            }
            for step in trajectory
            if step.action_type == ActionType.REPLAN
        ]

    def _extract_plan_updates(self, trajectory: List[TrajectoryStep]) -> List[Dict[str, Any]]:
        """Extract plan update events from trajectory."""
        return [
            {
                "step": step.step_number,
                "milestone_status": step.action_detail.get("milestone_status", {}),
                "next_action": step.action_detail.get("next_action", ""),
                "reason": step.action_detail.get("reason", ""),
                "remaining_steps": step.action_detail.get("remaining_steps", []),
            }
            for step in trajectory
            if step.action_type == ActionType.PLAN_UPDATE
        ]

    def _extract_tool_results(self, trajectory: List[TrajectoryStep]) -> List[Dict[str, Any]]:
        """Extract tool result events from trajectory."""
        return [
            {
                "step": step.step_number,
                "tool_name": step.action_detail.get("tool_name"),
                "success": step.action_detail.get("success", True),
                "error_type": step.action_detail.get("error_type"),
                "duration_ms": step.action_detail.get("duration_ms"),
                "output": step.observation,
            }
            for step in trajectory
            if step.action_type == ActionType.TOOL_RESULT
        ]

    def _extract_memory_events(self, trajectory: List[TrajectoryStep]) -> List[Dict[str, Any]]:
        """Extract memory read/write events from trajectory."""
        return [
            {
                "step": step.step_number,
                "type": step.action_type,
                "key": step.action_detail.get("key"),
                "value": step.action_detail.get("value"),
                "source": step.action_detail.get("source", ""),
                "context": step.action_detail.get("context", ""),
                "hit": step.action_detail.get("hit", True),
                "memory_type": step.action_detail.get("memory_type", ""),
            }
            for step in trajectory
            if step.action_type in (ActionType.MEMORY_WRITE, ActionType.MEMORY_READ)
        ]

    def _extract_state_changes(self, trajectory: List[TrajectoryStep]) -> List[Dict[str, Any]]:
        """Extract state change events from trajectory."""
        return [
            {
                "step": step.step_number,
                "node_name": step.action_detail.get("node_name", ""),
                "trigger": step.action_detail.get("trigger", ""),
                "diff": step.action_detail.get("diff", {}),
            }
            for step in trajectory
            if step.action_type == ActionType.STATE_CHANGE
        ]

    def _extract_failures(self, trajectory: List[TrajectoryStep]) -> List[Dict[str, Any]]:
        """Extract failure events from trajectory."""
        return [
            {
                "step": step.step_number,
                "error_type": step.action_detail.get("error_type", ""),
                "error_message": step.action_detail.get("error_message", ""),
                "context": step.action_detail.get("context", ""),
                "recoverable": step.action_detail.get("recoverable", True),
                "node_name": step.action_detail.get("node_name", ""),
            }
            for step in trajectory
            if step.action_type == ActionType.FAILURE
        ]

    def _extract_retrievals(self, trajectory: List[TrajectoryStep]) -> List[Dict[str, Any]]:
        """Extract knowledge retrieval events from trajectory."""
        return [
            {
                "step": step.step_number,
                "query": step.action_detail.get("query", ""),
                "source": step.action_detail.get("source", ""),
                "result_count": step.action_detail.get("result_count", 0),
                "duration_ms": step.action_detail.get("duration_ms"),
                "retrieved_docs": step.action_detail.get("retrieved_docs", []),
            }
            for step in trajectory
            if step.action_type == ActionType.RETRIEVAL
        ]

    def _extract_evidence(self, trajectory: List[TrajectoryStep]) -> List[Dict[str, Any]]:
        """Extract evidence pool events from trajectory."""
        return [
            {
                "step": step.step_number,
                "evidence_type": step.action_detail.get("evidence_type", ""),
                "context": step.action_detail.get("context", ""),
                "sources": step.action_detail.get("sources", {}),
                "final_prompt_messages": step.action_detail.get("final_prompt_messages", []),
                "total_message_count": step.action_detail.get("total_message_count", 0),
            }
            for step in trajectory
            if step.action_type == ActionType.EVIDENCE
        ]

    def _calculate_weighted_score(self, scores: Dict[str, float], weights: Dict[str, float]) -> float:
        """Calculate weighted average score."""
        total_weight = sum(weights.values())
        weighted_sum = sum(scores.get(k, 0) * v for k, v in weights.items())
        return weighted_sum / total_weight if total_weight > 0 else 0

    async def _invoke_llm_cached(self, chain, inputs: Dict[str, Any]) -> Any:
        """
        Invoke an LLM chain with Redis caching.

        If CACHE_LLM_RESPONSES is enabled and a cached response exists for the
        same prompt, return the cached content without calling the LLM.
        Otherwise, invoke the chain and cache the result.

        Args:
            chain: A LangChain runnable (prompt | llm).
            inputs: The input dict for the prompt template.

        Returns:
            The LLM response object (with .content attribute).
        """
        if not settings.CACHE_LLM_RESPONSES:
            return await chain.ainvoke(inputs)

        from app.core.cache import cache_hgetall, cache_hset, hash_prompt

        # Build a deterministic cache key from evaluator name + prompt content
        evaluator_name = type(self).__name__
        prompt_text = json.dumps(inputs, sort_keys=True, default=str)
        prompt_hash = hash_prompt(prompt_text)
        cache_key = f"llm:{evaluator_name}:{prompt_hash}"

        import time

        start_time = time.monotonic()

        # Check cache
        cached = await cache_hgetall(cache_key)
        if cached and "response" in cached:
            logger.debug("LLM cache hit: %s", cache_key)
            latency_ms = (time.monotonic() - start_time) * 1000
            # Store judge raw for cache hits too
            self._last_judge_raw = {
                "prompt": prompt_text[:10000],
                "response": cached["response"],
                "model": cached.get("model", "unknown"),
                "latency_ms": latency_ms,
                "cache_key": cache_key,
                "cached": True,
            }
            self._judge_raw_history.append(self._last_judge_raw)
            # Reconstruct a minimal response object with .content
            return _CachedLLMResponse(content=cached["response"])

        # Cache miss — call LLM
        logger.debug("LLM cache miss: %s", cache_key)
        start_time = time.monotonic()
        response = await chain.ainvoke(inputs)
        latency_ms = (time.monotonic() - start_time) * 1000

        # Store raw judge data for transparency
        model_name = getattr(self.llm, "model_name", "unknown")
        self._last_judge_raw = {
            "prompt": prompt_text[:10000],  # cap to avoid huge payloads
            "response": response.content[:10000],
            "model": model_name,
            "latency_ms": latency_ms,
            "cache_key": cache_key,
            "cached": False,
        }
        self._judge_raw_history.append(self._last_judge_raw)

        # Store in cache
        await cache_hset(
            cache_key,
            mapping={
                "response": response.content,
                "model": getattr(self.llm, "model_name", "unknown"),
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            ttl=settings.CACHE_LLM_TTL,
        )

        return response


class _CachedLLMResponse:
    """Minimal response wrapper for cached LLM output (mimics LangChain AIMessage.content)."""

    def __init__(self, content: str):
        self.content = content
