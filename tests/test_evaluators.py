"""
Tests for evaluator modules.
"""

import pytest
from datetime import datetime

from app.models.schemas import TrajectoryStep
from app.evaluators import (
    PlanningEvaluator,
    TacticalEvaluator,
    ToolUseEvaluator,
    MemoryEvaluator,
    ReplanEvaluator,
)


@pytest.fixture
def sample_trajectory():
    """Create sample trajectory for testing."""
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
            timestamp=datetime.utcnow(),
        ),
        TrajectoryStep(
            step_number=2,
            action_type="tool_call",
            action_detail={"tool_name": "search_code", "input": {"query": "authentication"}},
            observation="Found: auth.py, login.py, jwt_handler.py",
            timestamp=datetime.utcnow(),
        ),
        TrajectoryStep(
            step_number=3,
            action_type="tool_call",
            action_detail={"tool_name": "read_file", "input": {"file_path": "auth.py"}},
            observation="def authenticate(user, password):\n    # JWT authentication logic\n    token = generate_jwt(user)\n    return token",
            timestamp=datetime.utcnow(),
        ),
        TrajectoryStep(
            step_number=4,
            action_type="think",
            action_detail={"thought": "Found the auth code. Need to check JWT handling."},
            timestamp=datetime.utcnow(),
        ),
    ]


@pytest.mark.asyncio
async def test_planning_evaluator(sample_trajectory):
    """Test planning evaluator."""
    evaluator = PlanningEvaluator()

    # Mock LLM response
    class MockLLM:
        async def ainvoke(self, *args, **kwargs):
            class Response:
                content = '{"coverage": 80, "ordering": 85, "granularity": 75, "completeness": 80, "overall": 80, "feedback": "Good plan with clear steps."}'
            return Response()

    evaluator.llm = MockLLM()

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

    class MockLLM:
        async def ainvoke(self, *args, **kwargs):
            class Response:
                content = '{"relevance": 90, "efficiency": 85, "correctness": 88, "overall": 88, "feedback": "Good tactical decisions."}'
            return Response()

    evaluator.llm = MockLLM()

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

    class MockLLM:
        async def ainvoke(self, *args, **kwargs):
            class Response:
                content = '{"selection_quality": 92, "parameter_accuracy": 88, "result_utilization": 85, "overall": 89, "feedback": "Good tool usage."}'
            return Response()

    evaluator.llm = MockLLM()

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

    class MockLLM:
        async def ainvoke(self, *args, **kwargs):
            class Response:
                content = '{"retention": 85, "relevance": 90, "consistency": 88, "overall": 87, "feedback": "Good memory retention."}'
            return Response()

    evaluator.llm = MockLLM()

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

    class MockLLM:
        async def ainvoke(self, *args, **kwargs):
            class Response:
                content = '{"trigger_appropriateness": 100, "adaptation_quality": 100, "learning_from_failure": 100, "overall": 100, "feedback": "No replanning needed."}'
            return Response()

    evaluator.llm = MockLLM()

    result = await evaluator.evaluate(
        goal="Fix authentication bug",
        trajectory=sample_trajectory,
    )

    # No replans means perfect score for this dimension
    assert result.overall == 100
