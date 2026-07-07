"""
Retrieval Quality Evaluator — 第 6 评估维度

评估 Agent 的 RAG 检索质量：
- Relevance: 检索到的文档与问题的相关性
- Evidence Accuracy: 回答中引用的证据是否准确对应检索内容
- Coverage: 检索结果是否覆盖了回答问题所需的信息

基于 LLM-as-Judge，对比检索结果与 Agent 最终回答。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate

from app.evaluators.base import BaseEvaluator
from app.evaluators.eval_schemas import RetrievalEvaluationResult
from app.models.schemas import TrajectoryStep

logger = logging.getLogger(__name__)

# 尝试从 YAML 加载 Prompt，失败则使用硬编码 fallback
try:
    from prompts import get_prompt
    RETRIEVAL_EVAL_PROMPT = get_prompt("evaluators/retrieval")
except Exception:
    RETRIEVAL_EVAL_PROMPT = """你必须用中文输出所有内容（包括 feedback、missing_info）。你是一位 RAG（检索增强生成）质量评估专家。

## 问题 / 目标
{goal}

## 检索到的文档（来自知识库搜索）
{retrieved_docs}

## Agent 的最终回答
{final_answer}

## 评估标准

请从以下维度评分（0-100 分），严格按照锚点评分：

### 1. 相关性 (Relevance, 0-100)
检索到的文档与问题的相关程度。

| 分数 | 锚点表现 |
|------|----------|
| 0    | 所有检索文档与问题完全无关（如问认证问题，检索到数据库优化文档） |
| 25   | 大部分文档不相关（≥60%），仅 1-2 篇勉强沾边 |
| 50   | 相关性参差不齐：约一半文档直接相关，另一半不相关或边缘相关 |
| 75   | 大部分文档直接相关，仅 1 篇边缘相关或不相关 |
| 100  | 所有检索文档直接针对问题，零无关文档 |

### 2. 证据准确性 (Evidence Accuracy, 0-100)
回答是否准确引用/参考了检索内容？是否有幻觉？

| 分数 | 锚点表现 |
|------|----------|
| 0    | 严重幻觉：回答中的核心陈述与检索文档矛盾，或完全编造信息 |
| 25   | 大部分陈述缺少检索内容支撑（≥50%），存在多处幻觉 |
| 50   | 部分陈述有依据，但有 1-2 处添油加醋或无法从检索内容中推导 |
| 75   | 大部分陈述准确引用检索内容，仅 1 处轻微不准确或过度推断 |
| 100  | 所有陈述严格基于检索文档，零幻觉，引用准确无误 |

### 3. 覆盖度 (Coverage, 0-100)
检索到的文档是否包含回答问题的充分信息？

| 分数 | 锚点表现 |
|------|----------|
| 0    | 检索文档完全不包含回答问题所需的信息 |
| 25   | 仅覆盖了问题所需信息的 1-2 个方面，大量关键信息缺失 |
| 50   | 部分覆盖：核心信息存在，但有明显的信息缺口（如缺少配置方法、缺少错误处理） |
| 75   | 大部分信息存在，仅 1-2 个次要信息点缺失 |
| 100  | 检索文档包含回答问题所需的全部信息，零信息缺口 |

feedback 字段请用中文。hallucination_detected 标记是否检测到幻觉，missing_info 列出信息缺口。

{format_instructions}
"""


from app.models.schemas import RetrievalScore


class RetrievalEvaluator(BaseEvaluator):
    """检索质量评估器 (RAG Eval)。"""

    WEIGHTS = {
        "relevance": 0.35,
        "evidence_accuracy": 0.35,
        "coverage": 0.30,
    }

    async def evaluate(
        self,
        goal: str,
        trajectory: List[TrajectoryStep],
        context: Optional[Dict[str, Any]] = None,
    ) -> RetrievalScore:
        """评估 RAG 检索质量。

        从 trajectory 中提取 retrieval 动作和最终回答进行评估。

        Args:
            goal: 用户的原始目标
            trajectory: Agent 执行步骤列表
            context: 附加上下文

        Returns:
            包含详细评估结果的 RetrievalScore
        """
        # 提取检索结果
        retrievals = [
            s
            for s in trajectory
            if s.action_type in ("retrieval", "tool_call") and s.action_detail.get("retrieved_docs")
        ]
        retrieval_docs = []
        for s in retrievals:
            docs = s.action_detail.get("retrieved_docs", [])
            retrieval_docs.extend(docs)

        # 提取最终回答（最后一个 respond/think 步骤）
        final_answer = ""
        for s in reversed(trajectory):
            if s.action_type in ("think", "respond") and s.action_detail.get("thought"):
                final_answer = s.action_detail.get("thought", "")[:1000]
                break
        # Fallback: 从 observation 提取
        if not final_answer:
            for s in reversed(trajectory):
                if s.observation:
                    final_answer = str(s.observation)[:1000]
                    break

        if not retrieval_docs:
            return RetrievalScore(
                applicable=False,
                not_applicable_reason="轨迹中没有检索步骤，该维度已从综合评分中剔除。",
                overall=0,
                feedback="不适用：轨迹中没有检索步骤。",
            )

        # 格式化检索文档
        docs_text = "\n\n".join(
            f"[{i + 1}] {d.get('title', 'Unknown')}: {d.get('snippet', '')[:300]}"
            for i, d in enumerate(retrieval_docs[:10])
        )

        # 创建提示词 + 结构化输出链
        prompt = ChatPromptTemplate.from_template(RETRIEVAL_EVAL_PROMPT)
        structured_llm = self.llm.with_structured_output(RetrievalEvaluationResult)
        chain = prompt | structured_llm

        try:
            # 获取 LLM 评估结果（结构化输出 + 重试机制）
            result = await self._invoke_structured_llm(
                chain,
                {
                    "goal": goal,
                    "retrieved_docs": docs_text,
                    "final_answer": final_answer or "No final answer found",
                    "format_instructions": "",  # PydanticOutputParser 降级时会覆盖
                },
                schema_class=RetrievalEvaluationResult,
                max_retries=3,
                prompt=prompt,
            )

            # Pydantic model 直接使用
            scores = result.model_dump() if isinstance(result, RetrievalEvaluationResult) else result

            # 从 missing_info 中填充 llm_suggestions
            missing_info = scores.get("missing_info") or []
            llm_suggestions = [
                f"信息缺口：{info}" for info in missing_info if isinstance(info, str)
            ]
            scores["llm_suggestions"] = llm_suggestions

            return RetrievalScore(**scores)
        except Exception as e:
            logger.error("Retrieval evaluation failed: %s", e)
            return RetrievalScore(
                overall=0,
                feedback=f"Evaluation error: {str(e)}",
            )

    def _parse_scores(self, content: str) -> Dict[str, Any]:
        """解析 LLM 返回的 JSON（仅用于 fallback 场景）。"""
        data = self._parse_json_from_llm(content)
        if data is not None:
            try:
                overall = round(
                    data.get("relevance", 0) * self.WEIGHTS["relevance"]
                    + data.get("evidence_accuracy", 0) * self.WEIGHTS["evidence_accuracy"]
                    + data.get("coverage", 0) * self.WEIGHTS["coverage"],
                    1,
                )
                return {
                    "relevance": data.get("relevance", 50),
                    "evidence_accuracy": data.get("evidence_accuracy", 50),
                    "coverage": data.get("coverage", 50),
                    "overall": overall,
                    "feedback": data.get("feedback", ""),
                    "hallucination_detected": data.get("hallucination_detected", False),
                    "missing_info": data.get("missing_info", []),
                }
            except (KeyError, TypeError) as e:
                logger.warning("Failed to process retrieval eval scores: %s", e)
        return {
            "relevance": 50,
            "evidence_accuracy": 50,
            "coverage": 50,
            "overall": 50,
            "feedback": f"Parse error: {content[:200]}",
            "hallucination_detected": False,
            "missing_info": [],
        }
