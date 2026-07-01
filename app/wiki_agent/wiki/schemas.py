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
    summary: str = ""
    category: str = ""
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    source: str = "manual"
    created: str = ""
    updated: str = ""


class WikiPageCreate(BaseModel):
    """创建条目请求"""

    title: str
    content: str = ""
    summary: str = ""
    category: str = ""
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    source: str = "manual"


class WikiPageUpdate(BaseModel):
    """更新条目请求"""

    title: str | None = None
    content: str | None = None
    summary: str | None = None
    category: str | None = None
    aliases: list[str] | None = None
    tags: list[str] | None = None
    links: list[str] | None = None


class WikiCommit(BaseModel):
    """一次版本变更记录"""

    hash: str
    message: str
    date: str
    files: list[str] = Field(default_factory=list)
    parent_hash: str | None = None


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


class WikiBacklink(BaseModel):
    """反向链接：哪些页面引用了当前页"""

    path: str
    title: str
    snippet: str = ""


class WikiDiffLine(BaseModel):
    """Diff 中的一行"""

    type: str  # "add" | "remove" | "context"
    content: str
    old_line: int | None = None
    new_line: int | None = None


class WikiDiffHunk(BaseModel):
    """Diff 中的一个 hunk"""

    header: str = ""
    lines: list[WikiDiffLine] = Field(default_factory=list)


class WikiDiff(BaseModel):
    """两个版本之间的结构化 diff"""

    path: str
    old_hash: str
    new_hash: str
    old_content: str = ""
    new_content: str = ""
    hunks: list[WikiDiffHunk] = Field(default_factory=list)


class GraphNode(BaseModel):
    """知识图谱节点"""

    id: str
    title: str
    path: str
    category: str = ""
    tags: list[str] = Field(default_factory=list)


class GraphLink(BaseModel):
    """知识图谱边"""

    source: str
    target: str


class WikiGraph(BaseModel):
    """知识图谱数据"""

    nodes: list[GraphNode] = Field(default_factory=list)
    links: list[GraphLink] = Field(default_factory=list)


class TagInfo(BaseModel):
    """标签信息"""

    tag: str
    count: int
    pages: list[str] = Field(default_factory=list)


class CategoryInfo(BaseModel):
    """分类信息"""

    name: str
    path: str
    count: int
    children: list[CategoryInfo] = Field(default_factory=list)


class EntryIndexItem(BaseModel):
    """词条索引项"""

    title: str
    path: str
    summary: str = ""
    category: str = ""
