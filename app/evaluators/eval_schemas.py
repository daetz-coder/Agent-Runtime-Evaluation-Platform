"""
评估器 LLM 输出的 Pydantic Schema 定义。

供 PydanticOutputParser / 手工 JSON 解析校验 Judge 输出。
"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class InefficientCall(BaseModel):
    """低效工具调用记录，用于标记工具使用中的问题并提供改进建议。"""

    tool: str = Field(description="工具名称")
    issue: str = Field(description="问题描述，说明该调用为何低效")
    suggestion: str = Field(description="改进建议，提供更优的调用方式")


class ProblematicAction(BaseModel):
    """有问题的行动记录，用于标记战术决策中的问题。"""

    step: int = Field(description="步骤号")
    issue: str = Field(description="问题描述")
    suggestion: str = Field(description="改进建议")


class ReplanOpportunity(BaseModel):
    """重规划时机记录（错过或不必要的）。"""

    step: int = Field(description="步骤号")
    reason: str = Field(description="原因说明")


class ToolUseEvaluationResult(BaseModel):
    """工具使用评估器（ToolUseEvaluator）的结构化输出。

    衡量智能体选择工具、构造参数和利用返回结果的能力。
    """

    selection_quality: int = Field(ge=0, le=100, description="工具选择质量分数：是否选用了最合适的工具")
    parameter_accuracy: int = Field(ge=0, le=100, description="参数构造准确性分数：传入参数是否正确完整")
    result_utilization: int = Field(ge=0, le=100, description="结果利用分数：是否有效利用了工具返回值")
    overall: int = Field(ge=0, le=100, description="加权总分")
    feedback: str = Field(description="详细评估反馈，包含具体的优点和不足")
    inefficient_calls: List[InefficientCall] = Field(default_factory=list, description="低效工具调用列表")


class PlanningEvaluationResult(BaseModel):
    """规划评估器（PlanningEvaluator）的结构化输出。

    衡量智能体生成计划的覆盖度、顺序合理性、粒度和完整性。
    """

    coverage: int = Field(ge=0, le=100, description="覆盖度分数：计划是否涵盖了目标所需的所有关键步骤")
    ordering: int = Field(ge=0, le=100, description="顺序性分数：步骤排列是否符合逻辑依赖关系")
    granularity: int = Field(ge=0, le=100, description="粒度分数：步骤拆分是否足够细致可执行")
    completeness: int = Field(ge=0, le=100, description="完整性分数：计划是否包含了所有必要要素")
    overall: int = Field(ge=0, le=100, description="加权总分")
    feedback: str = Field(description="详细评估反馈")
    missing_milestones: List[str] = Field(default_factory=list, description="缺失的关键步骤列表")
    suggestions: List[str] = Field(default_factory=list, description="改进建议列表")


class TacticalEvaluationResult(BaseModel):
    """战术评估器（TacticalEvaluator）的结构化输出。

    衡量智能体在每一步动作决策中的相关性、效率和正确性。
    """

    relevance: int = Field(ge=0, le=100, description="相关性分数：当前动作是否与目标和计划相关")
    efficiency: int = Field(ge=0, le=100, description="效率分数：是否以最少步骤达成子目标")
    correctness: int = Field(ge=0, le=100, description="正确性分数：动作执行是否正确无误")
    overall: int = Field(ge=0, le=100, description="加权总分")
    feedback: str = Field(description="详细评估反馈")
    problematic_actions: List[ProblematicAction] = Field(default_factory=list, description="有问题的行动列表")


class MemoryEvaluationResult(BaseModel):
    """记忆评估器（MemoryEvaluator）的结构化输出。

    衡量智能体记忆系统的保持度、相关性和一致性。
    """

    retention: int = Field(ge=0, le=100, description="保持度分数：关键信息是否被正确存储并在需要时召回")
    relevance: int = Field(ge=0, le=100, description="相关性分数：存取的记忆内容是否与当前任务相关")
    consistency: int = Field(ge=0, le=100, description="一致性分数：记忆内容是否存在前后矛盾")
    overall: int = Field(ge=0, le=100, description="加权总分")
    feedback: str = Field(description="详细评估反馈")
    forgotten_facts: List[str] = Field(default_factory=list, description="被遗忘的重要事实列表")
    inconsistencies: List[str] = Field(default_factory=list, description="记忆不一致列表")


class ReplanEvaluationResult(BaseModel):
    """重规划评估器（ReplanEvaluator）的结构化输出。

    衡量智能体在遇到障碍或失败时触发重规划的时机、适应质量和从失败中学习的能力。
    """

    trigger_appropriateness: int = Field(ge=0, le=100, description="触发时机分数：是否在恰当的时机触发重规划")
    adaptation_quality: int = Field(ge=0, le=100, description="适应质量分数：新计划是否有效回应了遇到的问题")
    learning_from_failure: int = Field(ge=0, le=100, description="失败学习分数：是否从之前的失败中汲取了教训")
    overall: int = Field(ge=0, le=100, description="加权总分")
    feedback: str = Field(description="详细评估反馈")
    missed_replan_opportunities: List[ReplanOpportunity] = Field(default_factory=list, description="应触发但未触发的重规划时机")
    unnecessary_replans: List[ReplanOpportunity] = Field(default_factory=list, description="不必要的重规划记录")


class RetrievalEvaluationResult(BaseModel):
    """检索评估器（RetrievalEvaluator）的结构化输出。

    衡量智能体知识检索的相关性、证据准确性和覆盖度，并检测幻觉。
    """

    relevance: int = Field(ge=0, le=100, description="相关性分数：检索结果是否与查询意图相关")
    evidence_accuracy: int = Field(ge=0, le=100, description="证据准确分数：引用的证据是否准确可靠")
    coverage: int = Field(ge=0, le=100, description="覆盖度分数：检索结果是否覆盖了所需信息")
    overall: int = Field(ge=0, le=100, description="加权总分")
    feedback: str = Field(description="详细评估反馈")
    hallucination_detected: bool = Field(default=False, description="是否检测到模型产生了幻觉（无依据的编造）")
    missing_info: List[str] = Field(default_factory=list, description="信息缺口列表")


# ── Schema 注册表：评估器名称 → 对应的 Pydantic 输出 Schema ──

EVALUATOR_OUTPUT_SCHEMAS = {
    "tool_use": ToolUseEvaluationResult,
    "planning": PlanningEvaluationResult,
    "tactical": TacticalEvaluationResult,
    "memory": MemoryEvaluationResult,
    "replan": ReplanEvaluationResult,
    "retrieval": RetrievalEvaluationResult,
}
