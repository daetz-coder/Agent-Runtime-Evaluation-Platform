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

RETRIEVAL_EVAL_PROMPT = """你是一位 RAG（检索增强生成）质量评估专家。

## 问题 / 目标
{goal}

## 检索到的文档（来自知识库搜索）
{retrieved_docs}

## Agent 的最终回答
{final_answer}

## 评估标准

请从以下维度评分（0-100 分）：

1. **相关性** (Relevance, 0-100): 检索到的文档与问题的相关程度。
   - 100：所有检索文档直接针对问题
   - 70-90：大部分文档相关，少部分边缘相关
   - 40-70：相关性参差不齐，部分文档不相关
   - 0-40：大部分文档不相关

2. **证据准确性** (Evidence Accuracy, 0-100): 回答是否准确引用/参考了检索内容？
   - 100：所有陈述基于检索文档，无幻觉
   - 70-90：大部分有依据，少量添油加醋
   - 40-70：部分陈述缺少检索内容支撑
   - 0-40：严重幻觉或与检索文档矛盾

3. **覆盖度** (Coverage, 0-100): 检索到的文档是否包含回答问题的充分信息？
   - 100：检索文档包含所有所需信息
   - 70-90：大部分信息存在，少量缺口
   - 40-70：部分覆盖，明显信息不足
   - 0-40：检索文档完全不够

## 输出格式
返回 JSON 对象，feedback 字段请用中文：
{{
    "relevance": <分数>,
    "evidence_accuracy": <分数>,
    "coverage": <分数>,
    "overall": <三个维度的加权平均>,
    "feedback": "<详细评估反馈（中文）>",
    "hallucination_detected": <true/false>,
    "missing_info": ["信息缺口列表"]
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
                overall=0,
                feedback="No retrieval steps found in trajectory. Cannot evaluate RAG quality.",
            )

        # 格式化检索文档
        docs_text = "\n\n".join(
            f"[{i + 1}] {d.get('title', 'Unknown')}: {d.get('snippet', '')[:300]}"
            for i, d in enumerate(retrieval_docs[:10])
        )

        prompt = ChatPromptTemplate.from_template(RETRIEVAL_EVAL_PROMPT)
        chain = prompt | self.llm
        try:
            response = await self._invoke_llm_cached(
                chain,
                {
                    "goal": goal,
                    "retrieved_docs": docs_text,
                    "final_answer": final_answer or "No final answer found",
                },
            )
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
            "relevance": 50,
            "evidence_accuracy": 50,
            "coverage": 50,
            "overall": 50,
            "feedback": f"Parse error: {content[:200]}",
            "hallucination_detected": False,
            "missing_info": [],
        }
