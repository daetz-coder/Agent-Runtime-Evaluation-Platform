"""Wiki API 路由 — 写操作经 WikiSyncManager 同步 Markdown + Milvus + BM25 + Git"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.wiki_agent.agent.tools.sync_manager import sync_manager
from app.wiki_agent.wiki import git_service, service
from app.wiki_agent.wiki.schemas import (
    WikiCommit,
    WikiImportRequest,
    WikiNode,
    WikiPage,
    WikiPageCreate,
    WikiPageUpdate,
    WikiSearchResult,
)

router = APIRouter(prefix="/api/wiki", tags=["wiki"])


def _raise_on_sync_error(result: dict) -> None:
    """将 sync_manager 返回的错误映射为 HTTP 异常"""
    if result.get("status") != "error":
        return
    msg = result.get("message", "操作失败")
    if "已存在" in msg:
        raise HTTPException(409, msg)
    if "不存在" in msg:
        raise HTTPException(404, msg)
    raise HTTPException(500, msg)


# ── 目录树 ──────────────────────────────────────────────────


@router.get("/tree", response_model=WikiNode)
def get_tree(path: str = ""):
    """获取目录树结构"""
    return service.get_tree(path)


# ── 搜索 ────────────────────────────────────────────────────


@router.get("/search", response_model=list[WikiSearchResult])
def search(q: str = Query(..., min_length=1)):
    """搜索知识条目"""
    return service.search_pages(q)


# ── 版本管理（必须在 CRUD 之前，避免 {path:path} 贪婪匹配）───


@router.get("/history", response_model=list[WikiCommit])
def get_global_history(limit: int = 50):
    """获取整个知识库的变更历史"""
    return git_service.get_history(limit=limit)


@router.get("/page/{path:path}/history", response_model=list[WikiCommit])
def get_history(path: str, limit: int = 20):
    """获取条目变更历史"""
    return git_service.get_history(rel_path=path, limit=limit)


@router.post("/page/{path:path}/rollback")
def rollback(path: str, commit_hash: str):
    """回滚条目到指定版本，并同步 Milvus + BM25"""
    result = sync_manager.rollback(path, commit_hash)
    _raise_on_sync_error(result)
    return {"status": "ok", "message": f"已回滚到 {commit_hash}"}


# ── CRUD（经 WikiSyncManager 三端同步）──────────────────────


@router.get("/page/{path:path}", response_model=WikiPage)
def get_page(path: str):
    """读取知识条目"""
    try:
        return service.get_page(path)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@router.post("/page/{path:path}", response_model=WikiPage, status_code=201)
def create_page(path: str, data: WikiPageCreate):
    """创建知识条目"""
    result = sync_manager.create(
        path=path,
        title=data.title,
        content=data.content,
        tags=data.tags,
        source=data.source,
        git_message=f"新建条目: {data.title}",
    )
    _raise_on_sync_error(result)
    return service.get_page(path)


@router.put("/page/{path:path}", response_model=WikiPage)
def update_page(path: str, data: WikiPageUpdate):
    """更新知识条目"""
    result = sync_manager.update(
        path=path,
        title=data.title,
        content=data.content,
        tags=data.tags,
        links=data.links,
        git_message=f"更新条目: {data.title or path}",
    )
    _raise_on_sync_error(result)
    return service.get_page(path)


@router.delete("/page/{path:path}", status_code=204)
def delete_page(path: str):
    """删除知识条目"""
    result = sync_manager.delete(path, git_message=f"删除条目: {path}")
    _raise_on_sync_error(result)


# ── 导入 ────────────────────────────────────────────────────


@router.post("/import", response_model=WikiPage, status_code=201)
def import_markdown(data: WikiImportRequest):
    """导入 Markdown 内容"""
    result = sync_manager.import_markdown(
        path=data.path,
        content=data.content,
        source=data.source,
        overwrite=data.overwrite,
    )
    _raise_on_sync_error(result)
    return service.get_page(data.path)


# ── 自动标签 ────────────────────────────────────────────────


class AutoTagRequest(BaseModel):
    path: str


@router.post("/auto-tag")
async def auto_tag_page(data: AutoTagRequest):
    """为指定页面自动生成标签。"""
    from app.wiki_agent.agent.auto_tagger import generate_tags

    page = service.get_page(data.path)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    # 获取现有标签（遍历目录树收集所有标签）
    existing = set()

    def collect_tags(node):
        if hasattr(node, "tags") and node.tags:
            existing.update(node.tags)
        if hasattr(node, "children") and node.children:
            for child in node.children:
                collect_tags(child)

    tree = service.get_tree()
    collect_tags(tree)

    # 生成标签
    tags = await generate_tags(page.title, page.content, list(existing))
    if not tags:
        return {"path": data.path, "tags": page.tags or [], "auto_generated": False}

    # 更新页面标签
    import re

    content = page.content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            new_frontmatter = re.sub(
                r"^tags:.*$",
                "tags:\n" + "\n".join(f"- {t}" for t in tags),
                parts[1],
                flags=re.MULTILINE,
            )
            content = f"---{new_frontmatter}---{parts[2]}"

    from app.wiki_agent.agent.tools.sync_manager import sync_manager

    sync_manager.update(path=page.path, title=page.title, content=content, tags=tags)

    return {"path": data.path, "tags": tags, "auto_generated": True}


# ── 知识库导出 ──────────────────────────────────────────────


@router.get("/export")
def export_knowledge_base():
    """导出整个知识库为 Markdown 归档（ZIP 下载）。"""
    import io
    import zipfile

    from fastapi.responses import StreamingResponse

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:

        def add_pages(node, prefix=""):
            if hasattr(node, "path") and not getattr(node, "is_dir", True):
                page = service.get_page(node.path)
                if page:
                    zf.writestr(node.path, page.content or "")
            if hasattr(node, "children") and node.children:
                for child in node.children:
                    add_pages(child, prefix)

        tree = service.get_tree()
        add_pages(tree)

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=knowledge-base-export.zip"},
    )
