"""
Retrieval Quality Evaluator — 第 6 评估维度

评估 Agent 的 RAG 检索质量：
- Relevance: 检索到的文档与问题的相关性
- Evidence Accuracy: 回答中引用的证据是否准确对应检索内容
- Coverage: 检索结果是否覆盖了回答问题所需的信息

基于 LLM-as-Judge，对比检索结果与 Agent 最终回答。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.evaluators.base import BaseEvaluator
from app.models.schemas import TrajectoryStep

logger = logging.getLogger(__name__)

RETRIEVAL_EVAL_PROMPT = """You are an expert at evaluating RAG (Retrieval-Augmented Generation) quality.

## Question / Goal
{goal}

## Retrieved Documents (from knowledge base search)
{retrieved_docs}

## Agent's Final Answer
{final_answer}

## Evaluation Criteria

Evaluate on the following dimensions (0-100 scale):

1. **Relevance** (0-100): How relevant are the retrieved documents to the question?
   - 100: All retrieved docs directly address the question
   - 70-90: Most docs are relevant, some tangentially related
   - 40-70: Mixed relevance, several unrelated docs
   - 0-40: Most docs are irrelevant

2. **Evidence Accuracy** (0-100): Does the answer accurately cite/reference the retrieved content?
   - 100: All claims grounded in retrieved docs, no hallucination
   - 70-90: Most claims grounded, minor embellishments
   - 40-70: Some claims not supported by retrieved content
   - 0-40: Significant hallucination or contradiction with retrieved docs

3. **Coverage** (0-100): Do the retrieved documents contain sufficient information to answer the question?
   - 100: Retrieved docs contain all needed information
   - 70-90: Most info present, minor gaps
   - 40-70: Partial coverage, significant missing info
   - 0-40: Retrieved docs are insufficient

## Output Format
Return a JSON object:
{{
    "relevance": <score>,
    "evidence_accuracy": <score>,
    "coverage": <score>,
    "overall": <weighted average of the three>,
    "feedback": "<detailed feedback>",
    "hallucination_detected": <true/false>,
    "missing_info": ["list of information gaps"]
}}
"""


class RetrievalScore(BaseModel):
    """检索质量评估分。"""
    relevance: float = 0
    evidence_accuracy: float = 0
    coverage: float = 0
    overall: float = 0
    feedback: str = ""
    hallucination_detected: bool = False
    missing_info: List[str] = Field(default_factory=list)


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
        """
        # 提取检索结果
        retrievals = [
            s for s in trajectory
            if s.action_type in ("retrieval", "tool_call")
            and s.action_detail.get("retrieved_docs")
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
                overall=0,
                feedback="No retrieval steps found in trajectory. Cannot evaluate RAG quality.",
            )

        # 格式化检索文档
        docs_text = "\n\n".join(
            f"[{i+1}] {d.get('title', 'Unknown')}: {d.get('snippet', '')[:300]}"
            for i, d in enumerate(retrieval_docs[:10])
        )

        prompt = ChatPromptTemplate.from_template(RETRIEVAL_EVAL_PROMPT)
        chain = prompt | self.llm
        try:
            response = await self._invoke_llm_cached(chain, {
                "goal": goal,
                "retrieved_docs": docs_text,
                "final_answer": final_answer or "No final answer found",
            })
            scores = self._parse_scores(response.content)
            return RetrievalScore(**scores)
        except Exception as e:
            logger.error("Retrieval evaluation failed: %s", e)
            return RetrievalScore(
                overall=0,
                feedback=f"Evaluation error: {str(e)}",
            )

    def _parse_scores(self, content: str) -> Dict[str, Any]:
        """解析 LLM 返回的 JSON。"""
        try:
            import re
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                data = json.loads(match.group())
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
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Failed to parse retrieval eval: %s", e)
        return {
            "relevance": 50, "evidence_accuracy": 50, "coverage": 50,
            "overall": 50, "feedback": f"Parse error: {content[:200]}",
            "hallucination_detected": False, "missing_info": [],
        }
