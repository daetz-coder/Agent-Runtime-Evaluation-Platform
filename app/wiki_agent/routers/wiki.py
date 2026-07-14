"""Wiki API 路由 — 写操作经 WikiSyncManager 同步 Markdown + Milvus + BM25 + Git"""

from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, HTTPException, Query, UploadFile
from pydantic import BaseModel

from app.wiki_agent.agent.tools.sync_manager import sync_manager
from app.wiki_agent.config import settings
from app.wiki_agent.wiki import git_service, service
from app.wiki_agent.wiki.schemas import (
    CategoryInfo,
    TagInfo,
    WikiBacklink,
    WikiCommit,
    WikiDiff,
    WikiGraph,
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


@router.get("/page/{path:path}/diff", response_model=WikiDiff)
def get_diff(path: str, old: str = Query(...), new: str = Query("HEAD")):
    """获取两个版本之间的结构化 diff"""
    diff = git_service.get_structured_diff(path, old, new)
    return diff


@router.get("/page/{path:path}/backlinks", response_model=list[WikiBacklink])
def get_backlinks(path: str):
    """获取引用了当前页面的所有反向链接"""
    return service.get_backlinks(path)


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


# ── 标签 ────────────────────────────────────────────────────


@router.get("/tags", response_model=list[TagInfo])
def get_tags():
    """获取所有标签及其关联页面"""
    return service.get_all_tags()


# ── 知识图谱 ────────────────────────────────────────────────


@router.get("/graph", response_model=WikiGraph)
def get_graph():
    """获取知识图谱数据（节点 + 链接）"""
    return service.get_link_graph()


# ── 分类体系 ────────────────────────────────────────────────


@router.get("/categories", response_model=list[CategoryInfo])
def get_categories():
    """获取分类树"""
    return service.get_categories()


@router.get("/category/{category:path}/entries", response_model=list[WikiSearchResult])
def get_entries_by_category(category: str):
    """获取指定分类下的所有词条"""
    return service.get_entries_by_category(category)


# ── 词条索引 ────────────────────────────────────────────────


@router.get("/index")
def get_entry_index():
    """获取按首字母分组的词条索引"""
    return service.get_entry_index()


# ── 图片上传 ────────────────────────────────────────────────


@router.post("/upload")
async def upload_file(file: UploadFile):
    """上传图片/文件到知识库 assets 目录"""
    if not file.filename:
        raise HTTPException(400, "文件名为空")

    # 生成唯一文件名
    ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4().hex[:12]}{ext}"

    assets_dir = os.path.join(settings.KNOWLEDGE_DIR, "_assets")
    os.makedirs(assets_dir, exist_ok=True)

    file_path = os.path.join(assets_dir, filename)
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    return {"url": f"/api/wiki/assets/{filename}", "filename": filename}


@router.get("/assets/{filename}")
def get_asset(filename: str):
    """提供上传文件的静态访问"""
    from fastapi.responses import FileResponse

    file_path = os.path.join(settings.KNOWLEDGE_DIR, "_assets", filename)
    if not os.path.exists(file_path):
        raise HTTPException(404, "文件不存在")
    return FileResponse(file_path)
