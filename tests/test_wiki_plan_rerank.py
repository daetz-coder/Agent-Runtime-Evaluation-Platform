"""Tests for Wiki Agent plan generation and reranker model resolution."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.wiki_agent.agent import eval_middleware
from app.wiki_agent.agent.tools import reranker


@pytest.mark.asyncio
async def test_generate_plan_parses_structured_json() -> None:
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = """```json
{
  "plan": "分步实现脚本",
  "steps": [
    {"step": 1, "name": "分析需求", "description": "明确输入输出"},
    {"step": 2, "name": "编写代码", "description": "实现核心逻辑"}
  ],
  "estimated_complexity": "简单"
}
```"""
    chain = MagicMock()
    chain.ainvoke = AsyncMock(return_value=mock_response)

    with patch.object(eval_middleware, "_get_plan_llm", return_value=mock_llm):
        with patch("langchain_core.prompts.ChatPromptTemplate.from_template") as mock_template:
            mock_template.return_value.__or__ = MagicMock(return_value=chain)
            result = await eval_middleware._generate_plan("写一个 Python 脚本")

    assert result["plan"] == "分步实现脚本"
    assert len(result["steps"]) == 2
    assert result["steps"][0]["name"] == "分析需求"


@pytest.mark.asyncio
async def test_generate_plan_falls_back_when_llm_unavailable() -> None:
    with patch.object(eval_middleware, "_get_plan_llm", side_effect=ValueError("no api key")):
        result = await eval_middleware._generate_plan("测试目标")

    assert result == {"goal": "测试目标"}


def test_parse_plan_json_strips_markdown_fence() -> None:
    parsed = eval_middleware._parse_plan_json(
        '说明\n```json\n{"plan": "ok", "steps": [{"step": 1, "name": "a", "description": "b"}]}\n```'
    )
    assert parsed is not None
    assert parsed["plan"] == "ok"
    assert len(parsed["steps"]) == 1


def test_resolve_rerank_model_id_uses_hub_when_local_weights_missing(tmp_path: Path) -> None:
    local = tmp_path / "bge-reranker-base"
    local.mkdir()
    (local / "config.json").write_text("{}", encoding="utf-8")

    with patch.object(reranker.settings, "RERANK_MODEL_PATH", str(local)):
        with patch.object(reranker.settings, "RERANK_MODEL", "BAAI/bge-reranker-base"):
            assert reranker.resolve_rerank_model_id() == "BAAI/bge-reranker-base"


def test_resolve_rerank_model_id_uses_local_when_weights_present(tmp_path: Path) -> None:
    local = tmp_path / "bge-reranker-base"
    local.mkdir()
    (local / "model.safetensors").write_bytes(b"fake")

    with patch.object(reranker.settings, "RERANK_MODEL_PATH", str(local)):
        assert reranker.resolve_rerank_model_id() == str(local)


def test_get_reranker_status_reports_missing_weights(tmp_path: Path) -> None:
    local = tmp_path / "bge-reranker-base"
    local.mkdir()

    reranker._reranker_model = None
    reranker._reranker_load_error = "missing weights"

    with patch.object(reranker.settings, "RERANK_MODEL_PATH", str(local)):
        with patch.object(reranker.settings, "RERANK_ENABLED", True):
            status = reranker.get_reranker_status()

    assert status["enabled"] is True
    assert status["loaded"] is False
    assert status["has_local_weights"] is False
    assert status["error"] == "missing weights"
