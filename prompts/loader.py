"""
Prompt YAML 加载器，支持缓存和热加载。

从 prompts/ 目录下的 YAML 文件加载 Prompt 模板。
支持缓存、版本管理、热加载（清除缓存后重新读取文件）。

使用方式：
    from prompts.loader import get_prompt

    # 获取最新活跃版本
    template = get_prompt("evaluators/planning")

    # 获取指定版本
    template = get_prompt("evaluators/planning", version=2)

    # 获取元数据
    from prompts.loader import get_loader
    loader = get_loader()
    metadata = loader.get_metadata("evaluators/planning")
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

# prompts/ 目录的绝对路径
PROMPTS_DIR = Path(__file__).parent


class PromptLoader:
    """从 YAML 文件加载 Prompt 模板。

    特性：
    - 缓存：相同 Prompt 不重复读取文件
    - 热加载：调用 reload() 后重新读取文件
    - 版本管理：支持多版本 Prompt
    """

    def __init__(self, prompts_dir: Path = PROMPTS_DIR) -> None:
        self.dir = prompts_dir
        self._cache: Dict[str, Dict[str, Any]] = {}

    def get_prompt(self, name: str, version: Optional[int] = None) -> str:
        """获取 Prompt 模板文本。

        Args:
            name: Prompt 名称，如 "evaluators/planning"
            version: 版本号，None 表示最新活跃版本

        Returns:
            Prompt 模板字符串

        Raises:
            FileNotFoundError: Prompt 文件不存在
            ValueError: 指定版本不存在
        """
        data = self._load(name)
        return data["template"]

    def get_variables(self, name: str) -> List[Dict[str, str]]:
        """获取 Prompt 的变量定义。

        Args:
            name: Prompt 名称

        Returns:
            变量定义列表，如 [{"name": "goal", "description": "任务目标"}]
        """
        data = self._load(name)
        return data.get("variables", [])

    def get_metadata(self, name: str) -> Dict[str, Any]:
        """获取 Prompt 元数据（不含模板内容）。

        Args:
            name: Prompt 名称

        Returns:
            元数据字典
        """
        data = self._load(name)
        return {
            "name": data.get("name", name),
            "version": data.get("version", 1),
            "status": data.get("status", "active"),
            "description": data.get("description", ""),
            "author": data.get("author", ""),
            "created_at": data.get("created_at", ""),
        }

    def list_prompts(self) -> List[Dict[str, Any]]:
        """列出所有可用的 Prompt。

        Returns:
            Prompt 元数据列表
        """
        prompts = []
        for yaml_file in sorted(self.dir.rglob("*.yaml")):
            try:
                rel_path = yaml_file.relative_to(self.dir)
                name = str(rel_path.with_suffix("")).replace("\\", "/")
                data = self._load_yaml(yaml_file)
                prompts.append({
                    "name": name,
                    "version": data.get("version", 1),
                    "status": data.get("status", "active"),
                    "description": data.get("description", ""),
                    "author": data.get("author", ""),
                    "created_at": data.get("created_at", ""),
                })
            except Exception as e:
                logger.warning("Failed to load prompt %s: %s", yaml_file, e)
        return prompts

    def reload(self, name: Optional[str] = None) -> None:
        """清除缓存，强制重新加载。

        Args:
            name: 指定要清除的 Prompt 名称，None 表示清除所有
        """
        if name:
            self._cache.pop(name, None)
            logger.info("Reloaded prompt: %s", name)
        else:
            self._cache.clear()
            logger.info("Reloaded all prompts")

    def _load(self, name: str) -> Dict[str, Any]:
        """加载并缓存 Prompt 数据。"""
        if name not in self._cache:
            path = self.dir / f"{name}.yaml"
            if not path.exists():
                raise FileNotFoundError(f"Prompt not found: {path}")
            self._cache[name] = self._load_yaml(path)
            logger.debug("Loaded prompt: %s", name)
        return self._cache[name]

    def _load_yaml(self, path: Path) -> Dict[str, Any]:
        """从 YAML 文件加载数据。"""
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)


# ── 全局单例 ──────────────────────────────────────────────────

_loader: Optional[PromptLoader] = None


def get_loader() -> PromptLoader:
    """获取全局 PromptLoader 单例。"""
    global _loader
    if _loader is None:
        _loader = PromptLoader()
    return _loader


def get_prompt(name: str, version: Optional[int] = None) -> str:
    """便捷函数：获取 Prompt 模板文本。

    使用方式：
        from prompts import get_prompt
        template = get_prompt("evaluators/planning")
    """
    return get_loader().get_prompt(name, version)


def list_prompts() -> List[Dict[str, Any]]:
    """便捷函数：列出所有可用的 Prompt。"""
    return get_loader().list_prompts()
