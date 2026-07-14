"""Tests for evaluation prompt version stamp."""

from __future__ import annotations

from app.agent_runtime.prompts import PROMPT_VERSION


def test_prompt_version_format() -> None:
    assert PROMPT_VERSION.startswith("v")
    assert "." in PROMPT_VERSION
