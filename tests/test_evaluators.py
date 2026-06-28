"""
Tests for evaluator modules.
"""

from datetime import datetime
from typing import Any, List, Optional

import pytest
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from app.evaluators import (
    MemoryEvaluator,
    PlanningEvaluator,
    ReplanEvaluator,
    TacticalEvaluator,
    ToolUseEvaluator,
)
from app.models.schemas import TrajectoryStep


class MockLLM(BaseChatModel):
    """LangChain Runnable-compatible mock for evaluator unit tests."""

    response_json: str = "{}"

    @property
    def _llm_type(self) -> str:
        return "mock"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=self.response_json))])

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        return self._generate(messages, stop, run_manager, **kwargs)


@pytest.fixture
def sample_trajectory():
    """Create sample trajectory for testing."""
    from datetime import timezone

    return [
        TrajectoryStep(
            step_number=1,
            action_type="plan",
            action_detail={
                "goal": "Fix auth bug",
                "steps": [
                    {"description": "Search for auth code"},
                    {"description": "Read and analyze auth.py"},
                    {"description": "Identify the bug"},
                    {"description": "Implement fix"},
                    {"description": "Run tests"},
                ],
            },
            timestamp=datetime.now(timezone.utc),
        ),
        TrajectoryStep(
            step_number=2,
            action_type="tool_call",
            action_detail={"tool_name": "search_code", "input": {"query": "authentication"}},
            observation="Found: auth.py, login.py, jwt_handler.py",
            timestamp=datetime.now(timezone.utc),
        ),
        TrajectoryStep(
            step_number=3,
            action_type="tool_call",
            action_detail={"tool_name": "read_file", "input": {"file_path": "auth.py"}},
            observation="def authenticate(user, password):\n    # JWT authentication logic\n    token = generate_jwt(user)\n    return token",
            timestamp=datetime.now(timezone.utc),
        ),
        TrajectoryStep(
            step_number=4,
            action_type="think",
            action_detail={"thought": "Found the auth code. Need to check JWT handling."},
            timestamp=datetime.now(timezone.utc),
        ),
    ]


@pytest.mark.asyncio
async def test_planning_evaluator(sample_trajectory):
    """Test planning evaluator."""
    evaluator = PlanningEvaluator()
    evaluator.llm = MockLLM(
        response_json='{"coverage": 80, "ordering": 85, "granularity": 75, "completeness": 80, "overall": 80, "feedback": "Good plan with clear steps."}',
    )

    result = await evaluator.evaluate(
        goal="Fix authentication bug",
        trajectory=sample_trajectory,
    )

    assert result.coverage >= 0
    assert result.ordering >= 0
    assert result.granularity >= 0
    assert result.completeness >= 0
    assert result.overall >= 0
    assert result.feedback


@pytest.mark.asyncio
async def test_tactical_evaluator(sample_trajectory):
    """Test tactical evaluator."""
    evaluator = TacticalEvaluator()
    evaluator.llm = MockLLM(
        response_json='{"relevance": 90, "efficiency": 85, "correctness": 88, "overall": 88, "feedback": "Good tactical decisions."}',
    )

    result = await evaluator.evaluate(
        goal="Fix authentication bug",
        trajectory=sample_trajectory,
    )

    assert result.relevance >= 0
    assert result.efficiency >= 0
    assert result.correctness >= 0


@pytest.mark.asyncio
async def test_tool_use_evaluator(sample_trajectory):
    """Test tool use evaluator."""
    evaluator = ToolUseEvaluator()
    evaluator.llm = MockLLM(
        response_json='{"selection_quality": 92, "parameter_accuracy": 88, "result_utilization": 85, "overall": 89, "feedback": "Good tool usage."}',
    )

    result = await evaluator.evaluate(
        goal="Fix authentication bug",
        trajectory=sample_trajectory,
    )

    assert result.selection_quality >= 0
    assert result.parameter_accuracy >= 0
    assert result.result_utilization >= 0


@pytest.mark.asyncio
async def test_memory_evaluator(sample_trajectory):
    """Test memory evaluator."""
    evaluator = MemoryEvaluator()
    evaluator.llm = MockLLM(
        response_json='{"retention": 85, "relevance": 90, "consistency": 88, "overall": 87, "feedback": "Good memory retention."}',
    )

    result = await evaluator.evaluate(
        goal="Fix authentication bug",
        trajectory=sample_trajectory,
    )

    assert result.retention >= 0
    assert result.relevance >= 0
    assert result.consistency >= 0


@pytest.mark.asyncio
async def test_replan_evaluator_no_replans(sample_trajectory):
    """Test replan evaluator when no replans occurred."""
    evaluator = ReplanEvaluator()
    evaluator.llm = MockLLM(
        response_json='{"trigger_appropriateness": 100, "adaptation_quality": 100, "learning_from_failure": 100, "overall": 100, "feedback": "No replanning needed."}',
    )

    result = await evaluator.evaluate(
        goal="Fix authentication bug",
        trajectory=sample_trajectory,
    )

    # No replans means perfect score for this dimension
    assert result.overall == 100
