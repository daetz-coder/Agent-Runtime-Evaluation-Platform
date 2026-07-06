"""
Prompt Registry — Git-based Prompt 管理模块。

将所有 Prompt 模板集中存储在 YAML 文件中，支持：
- 版本控制（Git 天然支持）
- 热加载（修改 YAML 后无需重启服务）
- 缓存（避免重复读取文件）
- 元数据管理（版本号、状态、作者、描述）

使用方式：
    from prompts import get_prompt

    template = get_prompt("evaluators/planning")
    prompt = ChatPromptTemplate.from_template(template)
"""

from prompts.loader import PromptLoader, get_loader, get_prompt, list_prompts

__all__ = ["PromptLoader", "get_loader", "get_prompt", "list_prompts"]
