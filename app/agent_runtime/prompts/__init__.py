"""
Prompt Manager — file-based prompt templates with hot-reload.

Allows Agent engineers to edit prompts as YAML files without restarting
the server.  The PromptManager watches file modification times and
auto-refreshes its cache on read.

Usage:
    from app.agent_runtime.prompts import prompt_manager

    prompt = prompt_manager.get_prompt(version="v1.1")
    prompt_manager.list_versions()
    prompt_manager.save_prompt(version="v1.2", content="...")
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

# Default system prompt (used as fallback when file is missing)
_DEFAULT_SYSTEM_PROMPT = """\
You are an autonomous AI agent running inside a sandboxed environment.
Your workspace is at /workspace and you have access to tools for executing code, reading/writing files, and running commands.

## Your Goal
{goal}

{context_section}

## Available Tools
{tool_descriptions}

## Rules
1. **Plan before acting**: Start by creating a brief plan for how to achieve the goal.
2. **Use tools**: Use the available tools to execute your plan step by step.
3. **Observe results**: After each tool call, carefully observe the output and adjust your approach if needed.
4. **Handle errors**: If a tool call fails, analyze the error and try a different approach.
5. **Stay focused**: Work toward the goal efficiently — avoid unnecessary steps.
6. **Final answer**: When you have completed the goal, provide a clear final answer summarizing what was accomplished.

## Workspace
- Your working directory is /workspace
- All file operations are relative to /workspace
- Files you create will persist for the duration of the task
- You can read any files provided at the start of the task

## Output Format
- Think step by step about what to do next
- Make one tool call at a time and observe the result
- When the task is complete, provide your final answer
"""

_DEFAULT_CONTEXT_TEMPLATE = """\
## Additional Context
{context}
"""

_MODULE_DIR = Path(__file__).parent
_TEMPLATES_DIR = _MODULE_DIR / "templates"
_TEMPLATES_DIR.mkdir(exist_ok=True)

# Default version bundled with the package
_BUILTIN_VERSION = "v1.1"


class PromptManager:
    """File-based prompt template manager with hot-reload support."""

    def __init__(self, templates_dir: Optional[Path] = None) -> None:
        self._templates_dir = templates_dir or _TEMPLATES_DIR
        self._cache: Dict[str, str] = {}  # version → system_prompt
        self._context_cache: Dict[str, str] = {}  # version → context_template
        self._mtime: Dict[str, float] = {}  # version → last mtime

    # ── Public API ────────────────────────────────────────────

    def get_prompt(self, version: str = "") -> str:
        """Get the system prompt template for a version.

        Args:
            version: Prompt version string (e.g. "v1.1", "v1.2_experimental").
                     Empty string returns the built-in default.

        Returns:
            The system prompt template string, with ``{goal}``, ``{context_section}``,
            and ``{tool_descriptions}`` placeholders.
        """
        version = version or _BUILTIN_VERSION
        self._refresh_if_needed(version)
        return self._cache.get(version, _DEFAULT_SYSTEM_PROMPT)

    def get_context_template(self, version: str = "") -> str:
        """Get the context template for a version."""
        version = version or _BUILTIN_VERSION
        self._refresh_if_needed(version)
        return self._context_cache.get(version, _DEFAULT_CONTEXT_TEMPLATE)

    def list_versions(self) -> List[Dict[str, object]]:
        """List all available prompt versions with metadata."""
        versions: List[Dict[str, object]] = []
        for path in sorted(self._templates_dir.glob("*.yaml")):
            try:
                with open(path, encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                versions.append(
                    {
                        "version": data.get("version", path.stem),
                        "description": data.get("description", ""),
                        "file": path.name,
                        "updated_at": os.path.getmtime(path),
                    }
                )
            except Exception as e:
                logger.warning("Failed to read prompt template %s: %s", path.name, e)
        return versions

    def save_prompt(self, version: str, content: str, description: str = "") -> str:
        """Save a new prompt version as a YAML file.

        Args:
            version: Version identifier (e.g. "v1.2").
            content: The system prompt template (with ``{goal}`` etc.).
            description: Optional human-readable description.

        Returns:
            The file path where the prompt was saved.
        """
        data = {
            "version": version,
            "description": description,
            "prompt": content,
        }
        path = self._templates_dir / f"{version}.yaml"
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
        # Clear cache for this version
        self._cache.pop(version, None)
        self._mtime.pop(version, None)
        logger.info("Saved prompt version %s to %s", version, path)
        return str(path)

    # ── Internal ──────────────────────────────────────────────

    def _refresh_if_needed(self, version: str) -> None:
        """Reload a prompt template from disk if the file has changed."""
        path = self._templates_dir / f"{version}.yaml"
        if not path.exists():
            # Fall back to built-in default
            if version not in self._cache:
                self._cache[version] = _DEFAULT_SYSTEM_PROMPT
                self._context_cache[version] = _DEFAULT_CONTEXT_TEMPLATE
            return

        current_mtime = os.path.getmtime(path)
        cached_mtime = self._mtime.get(version)

        if cached_mtime == current_mtime and version in self._cache:
            return  # Cache is fresh

        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            self._cache[version] = data.get("prompt", _DEFAULT_SYSTEM_PROMPT)
            self._context_cache[version] = data.get("context_template", _DEFAULT_CONTEXT_TEMPLATE)
            self._mtime[version] = current_mtime
            logger.debug("Loaded prompt version %s from %s", version, path.name)
        except Exception as e:
            logger.warning("Failed to load prompt %s: %s — using default", version, e)
            self._cache[version] = _DEFAULT_SYSTEM_PROMPT
            self._context_cache[version] = _DEFAULT_CONTEXT_TEMPLATE


# ── Singleton ────────────────────────────────────────────────

prompt_manager = PromptManager()


def build_system_prompt(
    goal: str,
    tool_descriptions: str,
    context: str = "",
    version: str = "",
) -> str:
    """Build the agent system prompt with goal, tools, and optional context.

    Args:
        goal: The agent's goal/task.
        tool_descriptions: Formatted tool descriptions string.
        context: Optional extra context.
        version: Prompt version to use (empty = default).

    Returns:
        The fully rendered system prompt.
    """
    system_prompt = prompt_manager.get_prompt(version=version)
    context_template = prompt_manager.get_context_template(version=version)

    context_section = ""
    if context:
        context_section = context_template.format(context=context)

    return system_prompt.format(
        goal=goal,
        tool_descriptions=tool_descriptions,
        context_section=context_section,
    )


# Re-export for backward compatibility
PROMPT_VERSION = _BUILTIN_VERSION

FINAL_ANSWER_INSTRUCTION = (
    "If you have completed the goal, respond with your final answer. "
    "Prefix it with 'FINAL ANSWER:' so the system knows you are done."
)
