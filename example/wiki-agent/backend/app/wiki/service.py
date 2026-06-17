"""知识条目 CRUD 服务

所有知识条目以 Markdown 文件形式存储在 knowledge/ 目录下。
文件头部使用 YAML frontmatter 存储元数据（tags, links, source 等）。
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

import yaml

from app.config import settings
from app.wiki.schemas import (
    WikiNode,
    WikiPage,
    WikiPageCreate,
    WikiPageUpdate,
    WikiSearchResult,
)

KNOWLEDGE_DIR = Path(settings.KNOWLEDGE_DIR)
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _full_path(rel_path: str) -> Path:
    """将相对路径转为绝对路径，并做安全校验"""
    full = (KNOWLEDGE_DIR / rel_path).resolve()
    if not str(full).startswith(str(KNOWLEDGE_DIR.resolve())):
        raise ValueError("路径越界")
    return full


def _rel_path(full_path: Path) -> str:
    """将绝对路径转为相对路径"""
    return str(full_path.relative_to(KNOWLEDGE_DIR)).replace("\\", "/")


def _build_frontmatter(meta: dict) -> str:
    return "---\n" + yaml.dump(meta, allow_unicode=True, default_flow_style=False).strip() + "\n---\n"


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """解析 frontmatter，返回 (metadata, body)"""
    match = FRONTMATTER_RE.match(content)
    if match:
        try:
            meta = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError:
            meta = {}
        body = content[match.end():]
        return meta, body
    return {}, content


def _page_from_file(file_path: Path) -> WikiPage:
    """从 Markdown 文件读取为 WikiPage"""
    content = file_path.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(content)

    stat = file_path.stat()
    created = datetime.fromtimestamp(stat.st_ctime).isoformat(timespec="seconds")
    updated = datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds")

    return WikiPage(
        path=_rel_path(file_path),
        title=meta.get("title", file_path.stem),
        content=body.strip(),
        tags=meta.get("tags", []),
        links=meta.get("links", []),
        source=meta.get("source", "manual"),
        created=meta.get("created", created),
        updated=meta.get("updated", updated),
    )


def _file_from_page(page: WikiPage) -> str:
    """将 WikiPage 序列化为 Markdown 字符串（含 frontmatter）"""
    meta = {
        "title": page.title,
        "tags": page.tags,
        "links": page.links,
        "source": page.source,
        "created": page.created,
        "updated": page.updated or datetime.now().isoformat(timespec="seconds"),
    }
    return _build_frontmatter(meta) + page.content + "\n"


# ── 目录树 ──────────────────────────────────────────────────


def get_tree(rel_path: str = "") -> WikiNode:
    """获取目录树结构"""
    base = _full_path(rel_path) if rel_path else KNOWLEDGE_DIR
    _ensure_dir(base)

    root_name = rel_path if rel_path else "knowledge"
    node = WikiNode(name=root_name, path=rel_path, is_dir=True)

    entries = sorted(base.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    for entry in entries:
        if entry.name.startswith(".") or entry.name == ".git":
            continue
        entry_rel = _rel_path(entry)
        if entry.is_dir():
            node.children.append(get_tree(entry_rel))
        elif entry.suffix in (".md", ".txt"):
            node.children.append(
                WikiNode(name=entry.name, path=entry_rel, is_dir=False)
            )
    return node


# ── CRUD ────────────────────────────────────────────────────


def get_page(rel_path: str) -> WikiPage:
    full = _full_path(rel_path)
    if not full.exists():
        raise FileNotFoundError(f"条目不存在: {rel_path}")
    if full.is_dir():
        raise FileNotFoundError(f"路径是目录而非文件: {rel_path}")
    return _page_from_file(full)


def create_page(rel_path: str, data: WikiPageCreate) -> WikiPage:
    full = _full_path(rel_path)
    if full.exists():
        raise FileExistsError(f"条目已存在: {rel_path}")

    _ensure_dir(full.parent)
    now = datetime.now().isoformat(timespec="seconds")
    page = WikiPage(
        path=rel_path,
        title=data.title,
        content=data.content,
        tags=data.tags,
        source=data.source,
        created=now,
        updated=now,
    )
    full.write_text(_file_from_page(page), encoding="utf-8")
    return page


def update_page(rel_path: str, data: WikiPageUpdate) -> WikiPage:
    page = get_page(rel_path)
    if data.title is not None:
        page.title = data.title
    if data.content is not None:
        page.content = data.content
    if data.tags is not None:
        page.tags = data.tags
    if data.links is not None:
        page.links = data.links
    page.updated = datetime.now().isoformat(timespec="seconds")

    full = _full_path(rel_path)
    full.write_text(_file_from_page(page), encoding="utf-8")
    return page


def delete_page(rel_path: str) -> None:
    full = _full_path(rel_path)
    if not full.exists():
        raise FileNotFoundError(f"条目不存在: {rel_path}")
    full.unlink()


# ── 搜索 ────────────────────────────────────────────────────


def search_pages(query: str) -> list[WikiSearchResult]:
    """基于文件名 + 内容的简单全文搜索（MVP 阶段）"""
    import re
    results = []
    query_lower = query.lower()
    # 提取关键词（中文字符、英文单词、数字）
    keywords = re.findall(r'[一-鿿]+|[a-z]+|[0-9]+', query_lower)
    # 过滤掉太短的词（1个字符的中文、2个字符的英文）
    keywords = [k for k in keywords if len(k) > 1 or (len(k) == 1 and '一' <= k <= '鿿')]

    for md_file in KNOWLEDGE_DIR.rglob("*.md"):
        if ".git" in md_file.parts:
            continue
        try:
            content = md_file.read_text(encoding="utf-8")
        except Exception:
            continue

        score = 0.0
        rel = _rel_path(md_file)
        meta, body = _parse_frontmatter(content)
        title = meta.get("title", md_file.stem)
        stem_lower = md_file.stem.lower()
        title_lower = title.lower()
        body_lower = body.lower()

        # 完整查询匹配（高权重）
        if query_lower in stem_lower:
            score += 2.0
        if query_lower in title_lower:
            score += 3.0
        if query_lower in body_lower:
            score += 1.0

        # 关键词匹配
        for keyword in keywords:
            if keyword in stem_lower:
                score += 1.0
            if keyword in title_lower:
                score += 1.5
            if keyword in body_lower:
                score += 0.5

        # 提取匹配片段
        snippet = body[:100].replace("\n", " ").strip()
        for keyword in keywords:
            if keyword in body_lower:
                idx = body_lower.find(keyword)
                start = max(0, idx - 50)
                end = min(len(body), idx + len(keyword) + 50)
                snippet = body[start:end].replace("\n", " ").strip()
                break

        if score > 0:
            results.append(
                WikiSearchResult(path=rel, title=title, snippet=snippet, score=score)
            )

    results.sort(key=lambda r: r.score, reverse=True)
    return results[:20]


# ── 批量操作 ────────────────────────────────────────────────


def list_all_pages() -> list[str]:
    """列出所有条目的相对路径"""
    pages = []
    for md_file in sorted(KNOWLEDGE_DIR.rglob("*.md")):
        if ".git" not in md_file.parts:
            pages.append(_rel_path(md_file))
    return pages
