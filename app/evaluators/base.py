"""
所有评估维度的基类模块。

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
import re
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
    """所有评估器的抽象基类，提供 LLM 调用、轨迹解析和评分等通用能力。"""

    def __init__(self, llm: Optional[BaseChatModel] = None):
        """初始化评估器，可选传入自定义 LLM 实例。

        参数:
            llm: 可选的 LLM 模型实例，若不传则使用默认配置创建。
        """
        self.llm = llm or self._get_default_llm()
        # 保存最近一次 LLM 裁判的原始数据，用于透明度面板展示
        self._last_judge_raw: Optional[Dict[str, Any]] = None
        self._judge_raw_history: List[Dict[str, Any]] = []

    def get_last_judge_raw(self) -> Optional[Dict[str, Any]]:
        """返回最近一次 LLM 调用的原始 prompt/response 数据。"""
        return self._last_judge_raw

    def get_judge_raw_history(self) -> List[Dict[str, Any]]:
        """返回本次评估中所有 LLM 调用的原始数据记录。"""
        return list(self._judge_raw_history)

    def _get_default_llm(self) -> BaseChatModel:
        """根据配置文件中的 DEFAULT_LLM_PROVIDER 创建默认 LLM 实例。

        支持的供应商：anthropic、deepseek、glm（智谱）、qwen（通义千问）、openai。
        """
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
            # 通义千问 DashScope 接口兼容 OpenAI 协议
            return ChatOpenAI(
                model=settings.QWEN_MODEL,
                openai_api_key=settings.QWEN_API_KEY,
                openai_api_base=settings.QWEN_BASE_URL,
                temperature=0,
            )
        else:  # openai（默认供应商）
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
        """评估智能体行为（抽象方法，子类必须实现）。

        参数:
            goal: 原始目标/任务描述
            trajectory: 智能体执行步骤列表
            context: 评估所需的额外上下文信息

        返回:
            包含评分和反馈的字典
        """
        pass

    @staticmethod
    def _parse_json_from_llm(content: str) -> Optional[Dict[str, Any]]:
        """从 LLM 返回的文本中稳健地提取 JSON 对象。

        按顺序尝试三种策略：
        1. 从 ``json ... `` 围栏代码块中提取
        2. 从第一个 ``{`` 开始做花括号平衡匹配提取
        3. 贪心匹配第一个 ``{`` 到最后一个 ``}``（兜底方案）

        返回:
            解析成功返回字典，无法解析返回 None。
        """
        import json as _json

        # 策略 1：从围栏代码块中提取 JSON
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
        if match:
            try:
                return _json.loads(match.group(1))
            except _json.JSONDecodeError:
                pass

        # 策略 2：花括号平衡匹配
        start = content.find("{")
        if start != -1:
            depth = 0
            for i in range(start, len(content)):
                if content[i] == "{":
                    depth += 1
                elif content[i] == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return _json.loads(content[start : i + 1])
                        except _json.JSONDecodeError:
                            break

        # 策略 3：贪心兜底（兼容旧版格式）
        start = content.find("{")
        end = content.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return _json.loads(content[start:end])
            except _json.JSONDecodeError:
                pass

        return None

    def _format_trajectory(
        self,
        trajectory: List[TrajectoryStep],
        compress: bool = True,
    ) -> str:
        """将轨迹步骤格式化为可读文本。

        参数:
            trajectory: 轨迹步骤列表。
            compress: 为 True（默认）时，使用 4 阶段压缩管线处理；
                      为 False 时返回原始完整拼接输出。
        """
        if compress:
            compressor = TrajectoryCompressor()
            return compressor.compress(trajectory)
        return self._format_trajectory_raw(trajectory)

    @staticmethod
    def _format_trajectory_raw(trajectory: List[TrajectoryStep]) -> str:
        """完整拼接轨迹步骤，不进行压缩（压缩关闭时的兜底方案）。"""
        lines = []
        for step in trajectory:
            lines.append(f"Step {step.step_number} [{step.action_type}]:")
            lines.append(f"  Action: {step.action_detail}")
            if step.observation:
                lines.append(f"  Observation: {step.observation}")
            lines.append("")
        return "\n".join(lines)

    def _extract_plans(self, trajectory: List[TrajectoryStep]) -> List[Dict[str, Any]]:
        """从轨迹中提取规划步骤。

        会跳过"幽灵计划"——即仅包含 {goal, context} 而没有实际计划内容的条目，
        这些是任务创建时的附带产物，并非真正的规划。
        """
        plans = []
        for step in trajectory:
            if step.action_type == "plan":
                detail = step.action_detail
                if isinstance(detail, dict):
                    # 真正的计划至少包含 steps、milestones、plan、content 之一
                    has_structure = any(
                        detail.get(k) for k in ("steps", "milestones", "plan", "content")
                    )
                    if not has_structure and set(detail.keys()).issubset({"goal", "context"}):
                        continue  # 幽灵计划，跳过
                plans.append(detail)
        return plans

    def _extract_tool_calls(self, trajectory: List[TrajectoryStep]) -> List[Dict[str, Any]]:
        """从轨迹中提取工具调用步骤。"""
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
        """从轨迹中提取重规划事件。"""
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
        """从轨迹中提取计划更新事件。"""
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
        """从轨迹中提取工具执行结果事件。"""
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
        """从轨迹中提取记忆读写事件。"""
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
        """从轨迹中提取状态变化事件。"""
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
        """从轨迹中提取失败/异常事件。"""
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
        """从轨迹中提取知识检索事件。"""
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
        """从轨迹中提取证据池事件。"""
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
        """根据各维度分数和权重计算加权平均分。"""
        total_weight = sum(weights.values())
        weighted_sum = sum(scores.get(k, 0) * v for k, v in weights.items())
        return weighted_sum / total_weight if total_weight > 0 else 0

    async def _invoke_structured_llm(
        self,
        chain,
        inputs: Dict[str, Any],
        schema_class: type,
        max_retries: int = 3,
        prompt: Optional[Any] = None,
    ) -> Any:
        """调用结构化输出链，三级降级策略。

        降级顺序：
            1. with_structured_output（API 级 function calling，GPT-4/Claude 支持）
            2. PydanticOutputParser（prompt 注入 JSON Schema，DeepSeek 等模型可用）
            3. 手动 JSON 解析（最后兜底）

        参数:
            chain: LangChain runnable（prompt | structured_llm）
            inputs: prompt 输入
            schema_class: 期望的 Pydantic 输出 Schema
            max_retries: 每级策略的最大重试次数
            prompt: 原始 ChatPromptTemplate（用于 PydanticOutputParser 降级）
        """
        # ── 策略 1：with_structured_output ──
        result = await self._try_structured_output(chain, inputs, schema_class, max_retries)
        if result is not None:
            return result

        # ── 策略 2：PydanticOutputParser ──
        if prompt is not None:
            result = await self._try_pydantic_parser(prompt, inputs, schema_class, max_retries)
            if result is not None:
                return result

        # ── 策略 3：手动 JSON 解析 ──
        return await self._try_manual_parse(chain, inputs, schema_class)

    async def _try_structured_output(
        self, chain, inputs: Dict[str, Any], schema_class: type, max_retries: int
    ) -> Optional[Any]:
        """策略 1：with_structured_output（API 级 function calling）。"""
        last_error = None

        for attempt in range(max_retries):
            try:
                retry_inputs = dict(inputs)
                if attempt > 0 and last_error:
                    error_msg = (
                        f"\n\n⚠️ 上一次输出格式错误: {last_error}\n"
                        f"请严格按照 {schema_class.__name__} 的字段要求重新输出。"
                    )
                    if "context" in retry_inputs:
                        retry_inputs["context"] = str(retry_inputs["context"]) + error_msg
                    elif "goal" in retry_inputs:
                        retry_inputs["goal"] = str(retry_inputs["goal"]) + error_msg

                result = await chain.ainvoke(retry_inputs)

                if isinstance(result, schema_class):
                    return result
                if isinstance(result, dict):
                    return schema_class.model_validate(result)

                last_error = f"Expected {schema_class.__name__}, got {type(result).__name__}"
                logger.warning("Structured output attempt %d/%d: %s", attempt + 1, max_retries, last_error)

            except Exception as e:
                last_error = str(e)
                # 检测 API 不支持 structured output 的情况，立即降级
                if "response_format" in str(e).lower() or "unavailable" in str(e).lower():
                    logger.warning("Model does not support structured output, falling back to PydanticOutputParser")
                    return None
                logger.warning("Structured output attempt %d/%d failed: %s", attempt + 1, max_retries, last_error)

        logger.warning("Structured output failed after %d retries", max_retries)
        return None

    async def _try_pydantic_parser(
        self, prompt, inputs: Dict[str, Any], schema_class: type, max_retries: int
    ) -> Optional[Any]:
        """策略 2：PydanticOutputParser（prompt 注入 JSON Schema）。"""
        from langchain_core.output_parsers import PydanticOutputParser

        parser = PydanticOutputParser(pydantic_object=schema_class)

        # 注入 format_instructions 到 inputs
        parser_inputs = dict(inputs)
        parser_inputs["format_instructions"] = parser.get_format_instructions()

        last_error = None

        for attempt in range(max_retries):
            try:
                # 构建 chain：prompt | llm | parser
                chain = prompt | self.llm | parser

                if attempt > 0 and last_error:
                    error_msg = (
                        f"\n\n⚠️ 上一次输出格式错误: {last_error}\n"
                        f"请严格按照以下 JSON Schema 返回，不要截断。\n"
                        f"{parser.get_format_instructions()}"
                    )
                    if "context" in parser_inputs:
                        parser_inputs["context"] = str(parser_inputs["context"]) + error_msg
                    elif "goal" in parser_inputs:
                        parser_inputs["goal"] = str(parser_inputs["goal"]) + error_msg

                result = await chain.ainvoke(parser_inputs)

                if isinstance(result, schema_class):
                    logger.info("PydanticOutputParser succeeded on attempt %d", attempt + 1)
                    return result
                if isinstance(result, dict):
                    return schema_class.model_validate(result)

                last_error = f"Expected {schema_class.__name__}, got {type(result).__name__}"

            except Exception as e:
                last_error = str(e)
                logger.warning("PydanticOutputParser attempt %d/%d failed: %s", attempt + 1, max_retries, last_error)

        logger.warning("PydanticOutputParser failed after %d retries", max_retries)
        return None

    async def _try_manual_parse(
        self, chain, inputs: Dict[str, Any], schema_class: type
    ) -> Any:
        """策略 3：手动 JSON 解析（最后兜底）。"""
        logger.warning("Falling back to manual JSON parse for %s", schema_class.__name__)
        try:
            response = await self._invoke_llm_cached(chain, inputs)
            content = response.content if hasattr(response, "content") else str(response)
            scores = self._parse_json_from_llm(content)
            if scores:
                return schema_class.model_validate(scores)
        except Exception as e:
            logger.error("Manual parse also failed: %s", e)

        # 最终兜底：返回零分 + 错误信息
        return schema_class(
            **{k: 0 for k in schema_class.model_fields if k != "feedback"},
            feedback=f"评估输出解析失败",
        )

    async def _invoke_llm_cached(self, chain, inputs: Dict[str, Any]) -> Any:
        """调用 LLM 链并支持 Redis 缓存。

        若 CACHE_LLM_RESPONSES 开启且缓存中存在相同 prompt 的响应，
        则直接返回缓存内容而不调用 LLM；否则调用链并将结果写入缓存。

        参数:
            chain: LangChain runnable（prompt | llm）。
            inputs: prompt 模板的输入字典。

        返回:
            LLM 响应对象（包含 .content 属性）。
        """
        if not settings.CACHE_LLM_RESPONSES:
            return await chain.ainvoke(inputs)

        from app.core.cache import cache_hgetall, cache_hset, hash_prompt

        # 基于评估器名称 + 模型名 + prompt 内容构建确定性缓存键
        # 注意：model_name 至关重要——缺少它会导致多模型共识共享同一条缓存记录
        evaluator_name = type(self).__name__
        model_name = getattr(self.llm, "model_name", "unknown")
        prompt_text = json.dumps(inputs, sort_keys=True, default=str)
        prompt_hash = hash_prompt(prompt_text)
        cache_key = f"llm:{evaluator_name}:{model_name}:{prompt_hash}"

        import time

        start_time = time.monotonic()

        # 查询缓存
        cached = await cache_hgetall(cache_key)
        if cached and "response" in cached:
            logger.debug("LLM 缓存命中: %s", cache_key)
            latency_ms = (time.monotonic() - start_time) * 1000
            # 缓存命中时也需要保存裁判原始数据
            self._last_judge_raw = {
                "prompt": prompt_text[:10000],
                "response": cached["response"],
                "model": cached.get("model", "unknown"),
                "latency_ms": latency_ms,
                "cache_key": cache_key,
                "cached": True,
            }
            self._judge_raw_history.append(self._last_judge_raw)
            # 构造最小响应对象，模拟 LangChain AIMessage.content
            return _CachedLLMResponse(content=cached["response"])

        # 缓存未命中，调用 LLM
        logger.debug("LLM 缓存未命中: %s", cache_key)
        start_time = time.monotonic()
        response = await chain.ainvoke(inputs)
        latency_ms = (time.monotonic() - start_time) * 1000

        # 保存裁判原始数据，用于透明度面板展示
        self._last_judge_raw = {
            "prompt": prompt_text[:10000],  # 截断避免过大载荷
            "response": response.content[:10000],
            "model": model_name,
            "latency_ms": latency_ms,
            "cache_key": cache_key,
            "cached": False,
        }
        self._judge_raw_history.append(self._last_judge_raw)

        # 写入缓存
        await cache_hset(
            cache_key,
            mapping={
                "response": response.content,
                "model": model_name,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            ttl=settings.CACHE_LLM_TTL,
        )

        return response


class _CachedLLMResponse:
    """缓存命中时使用的最小响应包装类，模拟 LangChain AIMessage.content 接口。"""

    def __init__(self, content: str):
        self.content = content
