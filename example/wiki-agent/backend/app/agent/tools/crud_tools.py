"""CRUD 工具 — 知识条目的增删改查操作

所有操作都通过 WikiSyncManager 执行，确保 Markdown + ChromaDB + Git 一致性
"""

from __future__ import annotations

from app.agent.tools.sync_manager import sync_manager
from app.wiki import service


def read_knowledge(path: str) -> dict | None:
    """读取知识条目

    Args:
        path: 知识条目路径

    Returns:
        dict: 知识条目内容，不存在返回 None
    """
    try:
        page = service.get_page(path)
        return {
            "status": "ok",
            "path": page.path,
            "title": page.title,
            "content": page.content,
            "tags": page.tags,
            "created": page.created,
            "updated": page.updated,
        }
    except FileNotFoundError:
        return None


def create_knowledge(
    title: str,
    content: str,
    category: str = "",
    tags: list[str] | None = None,
    source: str = "agent",
) -> dict:
    """创建知识条目

    Args:
        title: 条目标题
        content: Markdown 内容
        category: 分类路径
        tags: 标签列表
        source: 来源

    Returns:
        dict: 创建结果
    """
    # 生成安全路径
    safe_title = title.strip().lower().replace(" ", "-")
    safe_title = "".join(c for c in safe_title if c.isalnum() or c in "-_一-龥")
    prefix = category.strip().rstrip("/") or "notes"
    path = f"{prefix}/{safe_title}.md"

    # 检查是否已存在
    existing = read_knowledge(path)
    if existing:
        return {
            "status": "ok",
            "action": "exists",
            "path": path,
            "message": f"条目已存在: {existing['title']}",
        }

    return sync_manager.create(
        path=path,
        title=title,
        content=content,
        tags=tags,
        source=source,
    )


def update_knowledge(
    path: str,
    title: str | None = None,
    content: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """更新知识条目

    Args:
        path: 知识条目路径
        title: 新标题（可选）
        content: 新内容（可选）
        tags: 新标签（可选）

    Returns:
        dict: 更新结果
    """
    return sync_manager.update(
        path=path,
        title=title,
        content=content,
        tags=tags,
    )


def delete_knowledge(path: str) -> dict:
    """删除知识条目

    Args:
        path: 知识条目路径

    Returns:
        dict: 删除结果
    """
    return sync_manager.delete(path)


def list_knowledge(category: str = "") -> list[dict]:
    """列出知识条目

    Args:
        category: 分类路径（可选，为空则列出所有）

    Returns:
        list[dict]: 知识条目列表
    """
    try:
        tree = service.get_tree(category)
        return _flatten_tree(tree)
    except Exception as e:
        print(f"[CRUD] 列出知识失败: {e}")
        return []


def get_knowledge_tree() -> dict:
    """获取知识库目录树

    Returns:
        dict: 目录树结构
    """
    try:
        tree = service.get_tree()
        return _tree_to_dict(tree)
    except Exception as e:
        print(f"[CRUD] 获取目录树失败: {e}")
        return {}


def _flatten_tree(node) -> list[dict]:
    """递归展平目录树为列表"""
    result = []
    if not node.is_dir:
        result.append({
            "path": node.path,
            "name": node.name,
            "is_dir": False,
        })
    if node.children:
        for child in node.children:
            result.extend(_flatten_tree(child))
    return result


def _tree_to_dict(node) -> dict:
    """递归转换目录树为字典"""
    result = {
        "name": node.name,
        "path": node.path,
        "is_dir": node.is_dir,
    }
    if node.children:
        result["children"] = [_tree_to_dict(child) for child in node.children]
    return result
