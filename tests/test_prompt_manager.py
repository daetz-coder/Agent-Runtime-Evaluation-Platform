"""Tests for PromptManager — file-based hot-reload prompt templates."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from app.agent_runtime.prompts import PROMPT_VERSION, PromptManager, build_system_prompt, prompt_manager


class TestPromptManager:
    """Tests for the hot-reload prompt manager."""

    def setup_method(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.mgr = PromptManager(templates_dir=self.tmp_dir)

    def teardown_method(self):
        import shutil

        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_get_prompt_returns_default_when_no_file(self):
        """Should fall back to built-in default when no file exists."""
        prompt = self.mgr.get_prompt("v1.1")
        assert "{goal}" in prompt
        assert "{tool_descriptions}" in prompt

    def test_get_prompt_loads_from_file(self):
        """Should load prompt from YAML file if it exists."""
        data = {
            "version": "v1.2",
            "description": "Experimental prompt",
            "prompt": "Custom prompt {goal} {tool_descriptions} {context_section}",
        }
        path = self.tmp_dir / "v1.2.yaml"
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f)

        prompt = self.mgr.get_prompt("v1.2")
        assert prompt == "Custom prompt {goal} {tool_descriptions} {context_section}"

    def test_get_prompt_hot_reload(self):
        """Should detect file changes and reload automatically."""
        # Write initial version
        data = {"version": "v1.3", "prompt": "Version A {goal}"}
        path = self.tmp_dir / "v1.3.yaml"
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f)

        assert self.mgr.get_prompt("v1.3") == "Version A {goal}"

        # Modify file (simulate user editing)
        data["prompt"] = "Version B {goal}"
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f)

        # Should pick up change without explicit reload
        assert self.mgr.get_prompt("v1.3") == "Version B {goal}"

    def test_save_prompt_creates_file(self):
        """Should create a new YAML file when saving."""
        path = self.mgr.save_prompt("v1.5", "New prompt {goal}", description="Test")
        assert Path(path).exists()
        assert self.mgr.get_prompt("v1.5") == "New prompt {goal}"

    def test_save_prompt_overwrites(self):
        """Should overwrite an existing prompt file."""
        self.mgr.save_prompt("v1.6", "Old version")
        self.mgr.save_prompt("v1.6", "New version")
        assert self.mgr.get_prompt("v1.6") == "New version"

    def test_list_versions_empty(self):
        """Should return empty list when no templates exist."""
        versions = self.mgr.list_versions()
        assert versions == []

    def test_list_versions(self):
        """Should list saved template versions."""
        self.mgr.save_prompt("v1.a", "Content A", description="Desc A")
        self.mgr.save_prompt("v1.b", "Content B", description="Desc B")

        versions = self.mgr.list_versions()
        assert len(versions) >= 2
        version_names = [v["version"] for v in versions]
        assert "v1.a" in version_names
        assert "v1.b" in version_names

    def test_get_context_template_default(self):
        """Should return default context template when no file exists."""
        ctx = self.mgr.get_context_template("nonexistent")
        assert "{context}" in ctx

    def test_build_system_prompt_integration(self):
        """build_system_prompt should produce a fully rendered prompt."""
        # Save a template
        self.mgr.save_prompt(
            "v1.test",
            "System: {goal} | Tools: {tool_descriptions} | {context_section}",
        )
        result = build_system_prompt(
            goal="Test goal",
            tool_descriptions="python, bash",
            context="Extra context",
            version="v1.test",
        )
        assert "Test goal" in result
        assert "python, bash" in result
        assert "Extra context" in result

    def test_build_system_prompt_no_context(self):
        """Should work without context."""
        result = build_system_prompt(
            goal="Test",
            tool_descriptions="None",
            version="v1.1",
        )
        assert "Test" in result

    def test_prompt_version_constant(self):
        """PROMPT_VERSION should be a valid version string."""
        assert PROMPT_VERSION.startswith("v")
        assert "." in PROMPT_VERSION

    def test_singleton_available(self):
        """Module-level prompt_manager should be initialized."""
        assert prompt_manager is not None
        assert isinstance(prompt_manager, PromptManager)
