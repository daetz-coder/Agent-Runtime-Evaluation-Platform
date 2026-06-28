"""
Detect code-execution tool calls in agent trajectories.

Maintains a registry of known code-execution tool name patterns and
extracts the code + language from the tool call's input payload.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.sandbox.models import SandboxLanguage

# Tool name patterns that indicate code execution.
# Order matters — first match wins.
_CODE_TOOL_PATTERNS: list[tuple[re.Pattern, SandboxLanguage]] = [
    (
        re.compile(r"(run_python|execute_python|python_exec|python_repl|run_code|execute_code)", re.I),
        SandboxLanguage.PYTHON,
    ),
    (re.compile(r"(bash|shell|run_shell|run_bash|execute_shell|terminal|run_command)", re.I), SandboxLanguage.BASH),
    (re.compile(r"(run_node|execute_js|node_exec|run_javascript)", re.I), SandboxLanguage.NODE),
]

# Keys within the tool call `input` dict that typically contain code.
_CODE_KEYS = ["code", "command", "script", "query", "input", "body"]


@dataclass
class DetectedCodeSnippet:
    """A code snippet extracted from a trajectory tool call."""

    step: int
    tool_name: str
    language: SandboxLanguage
    code: str
    original_output: str  # What the agent recorded as output (for comparison)


def detect_code_executions(tool_calls: List[Dict[str, Any]]) -> List[DetectedCodeSnippet]:
    """
    Scan a list of tool calls and return those that look like code execution.

    Args:
        tool_calls: List of dicts with keys {step, tool, input, output}
                    (same shape as BaseEvaluator._extract_tool_calls output)

    Returns:
        List of DetectedCodeSnippet for each code-execution tool call found.
    """
    results: list[DetectedCodeSnippet] = []

    for call in tool_calls:
        tool_name = call.get("tool", "")
        if not tool_name:
            continue

        matched_lang: Optional[SandboxLanguage] = None
        for pattern, lang in _CODE_TOOL_PATTERNS:
            if pattern.search(tool_name):
                matched_lang = lang
                break

        if matched_lang is None:
            continue

        code = _extract_code(call.get("input", {}))
        if not code or not code.strip():
            continue

        results.append(
            DetectedCodeSnippet(
                step=call.get("step", 0),
                tool_name=tool_name,
                language=matched_lang,
                code=code,
                original_output=str(call.get("output", "") or ""),
            )
        )

    return results


def _extract_code(input_data: Any) -> str:
    """Pull code text out of a tool-call input payload."""
    if isinstance(input_data, str):
        return input_data
    if isinstance(input_data, dict):
        for key in _CODE_KEYS:
            value = input_data.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return ""
