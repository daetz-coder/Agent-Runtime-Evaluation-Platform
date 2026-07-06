"""Prompt Registry 测试 — 验证 YAML 加载、缓存、列表功能。"""

from __future__ import annotations

import pytest
from pathlib import Path

from prompts.loader import PromptLoader


@pytest.fixture
def loader():
    """使用真实的 prompts/ 目录创建 PromptLoader。"""
    return PromptLoader()


class TestPromptLoader:
    """PromptLoader 核心功能测试。"""

    def test_list_prompts(self, loader: PromptLoader):
        """应该能列出所有 Prompt。"""
        prompts = loader.list_prompts()
        assert len(prompts) > 0

        # 验证返回结构
        for p in prompts:
            assert "name" in p
            assert "version" in p
            assert "status" in p
            assert "description" in p

    def test_get_prompt_evaluators(self, loader: PromptLoader):
        """应该能加载所有评估器 Prompt。"""
        evaluator_names = [
            "evaluators/planning",
            "evaluators/tactical",
            "evaluators/tool_use",
            "evaluators/memory",
            "evaluators/replan",
            "evaluators/retrieval",
        ]
        for name in evaluator_names:
            template = loader.get_prompt(name)
            assert isinstance(template, str)
            assert len(template) > 100, f"{name} template too short"
            # 验证包含 format_instructions 占位符
            assert "{format_instructions}" in template, f"{name} missing format_instructions"

    def test_get_prompt_wiki_agent(self, loader: PromptLoader):
        """应该能加载所有 Wiki Agent Prompt。"""
        wiki_names = [
            "wiki_agent/system_prompt",
            "wiki_agent/key_facts",
            "wiki_agent/decide",
            "wiki_agent/auto_tag",
            "wiki_agent/query_rewrite",
        ]
        for name in wiki_names:
            template = loader.get_prompt(name)
            assert isinstance(template, str)
            assert len(template) > 50, f"{name} template too short"

    def test_get_metadata(self, loader: PromptLoader):
        """应该能获取 Prompt 元数据。"""
        metadata = loader.get_metadata("evaluators/planning")
        assert metadata["name"] == "evaluators/planning"
        assert metadata["version"] == 1
        assert metadata["status"] == "active"
        assert len(metadata["description"]) > 0

    def test_get_variables(self, loader: PromptLoader):
        """应该能获取 Prompt 变量定义。"""
        variables = loader.get_variables("evaluators/planning")
        assert len(variables) > 0
        # 验证变量结构
        for var in variables:
            assert "name" in var
            assert "description" in var

    def test_cache(self, loader: PromptLoader):
        """相同 Prompt 应该从缓存读取。"""
        # 第一次加载
        template1 = loader.get_prompt("evaluators/planning")
        # 第二次加载（应该从缓存）
        template2 = loader.get_prompt("evaluators/planning")
        assert template1 == template2

    def test_reload(self, loader: PromptLoader):
        """reload() 应该清除缓存。"""
        # 加载一次
        loader.get_prompt("evaluators/planning")
        # 清除缓存
        loader.reload("evaluators/planning")
        # 应该重新加载
        template = loader.get_prompt("evaluators/planning")
        assert isinstance(template, str)

    def test_file_not_found(self, loader: PromptLoader):
        """不存在的 Prompt 应该抛出 FileNotFoundError。"""
        with pytest.raises(FileNotFoundError):
            loader.get_prompt("nonexistent/prompt")

    def test_convenience_function(self):
        """便捷函数 get_prompt() 应该正常工作。"""
        from prompts import get_prompt
        template = get_prompt("evaluators/planning")
        assert isinstance(template, str)
        assert len(template) > 100

    def test_convenience_list_function(self):
        """便捷函数 list_prompts() 应该正常工作。"""
        from prompts import list_prompts
        prompts = list_prompts()
        assert len(prompts) > 0
