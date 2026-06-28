from __future__ import annotations

from pydantic import BaseModel, Field


class WikiNode(BaseModel):
    """目录树中的一个节点"""

    name: str
    path: str
    is_dir: bool
    children: list[WikiNode] = Field(default_factory=list)


class WikiPage(BaseModel):
    """一条知识条目"""

    path: str
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    source: str = "manual"
    created: str = ""
    updated: str = ""


class WikiPageCreate(BaseModel):
    """创建条目请求"""

    title: str
    content: str = ""
    tags: list[str] = Field(default_factory=list)
    source: str = "manual"


class WikiPageUpdate(BaseModel):
    """更新条目请求"""

    title: str | None = None
    content: str | None = None
    tags: list[str] | None = None
    links: list[str] | None = None


class WikiCommit(BaseModel):
    """一次版本变更记录"""

    hash: str
    message: str
    date: str
    files: list[str] = Field(default_factory=list)


class WikiSearchResult(BaseModel):
    """搜索结果"""

    path: str
    title: str
    snippet: str
    score: float = 0.0


class WikiImportRequest(BaseModel):
    """导入 Markdown 请求"""

    path: str
    content: str
    source: str = "import"
    overwrite: bool = False


class WikiExtractConfirm(BaseModel):
    """确认提取的知识点"""

    session_id: str
    items: list[WikiPageCreate]
