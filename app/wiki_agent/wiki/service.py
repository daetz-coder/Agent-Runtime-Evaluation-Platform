"""知识条目 CRUD 服务

所有知识条目以 Markdown 文件形式存储在 knowledge/ 目录下。
文件头部使用 YAML frontmatter 存储元数据（tags, links, source 等）。
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import yaml

from app.wiki_agent.config import settings
from app.wiki_agent.wiki.schemas import (
    EntryIndexItem,
    GraphLink,
    GraphNode,
    TagInfo,
    WikiBacklink,
    WikiGraph,
    WikiNode,
    WikiPage,
    WikiPageCreate,
    WikiPageUpdate,
    WikiSearchResult,
)

KNOWLEDGE_DIR = Path(settings.KNOWLEDGE_DIR)
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


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
        body = content[match.end() :]
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
        summary=meta.get("summary", ""),
        category=meta.get("category", ""),
        aliases=meta.get("aliases", []),
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
        "summary": page.summary,
        "category": page.category,
        "aliases": page.aliases,
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
            node.children.append(WikiNode(name=entry.name, path=entry_rel, is_dir=False))
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
        summary=data.summary,
        category=data.category,
        aliases=data.aliases,
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
    if data.summary is not None:
        page.summary = data.summary
    if data.category is not None:
        page.category = data.category
    if data.aliases is not None:
        page.aliases = data.aliases
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
    keywords = re.findall(r"[一-鿿]+|[a-z]+|[0-9]+", query_lower)
    # 过滤掉太短的词（1个字符的中文、2个字符的英文）
    keywords = [k for k in keywords if len(k) > 1 or (len(k) == 1 and "一" <= k <= "鿿")]

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
            results.append(WikiSearchResult(path=rel, title=title, snippet=snippet, score=score))

    results.sort(key=lambda r: r.score, reverse=True)
    return results[:20]


# ── Wiki Links ─────────────────────────────────────────────


def extract_wikilinks(content: str) -> list[str]:
    """从 Markdown 内容中提取所有 [[...]] 链接目标"""
    return WIKILINK_RE.findall(content)


def resolve_link(target: str) -> str | None:
    """将 [[target]] 解析为相对路径。

    匹配优先级：
    1. 精确匹配文件路径（去掉 .md 后缀）
    2. 匹配 frontmatter 中的 title 字段
    3. 匹配文件名（stem）
    """
    target_lower = target.lower().strip()

    for md_file in KNOWLEDGE_DIR.rglob("*.md"):
        if ".git" in md_file.parts:
            continue
        rel = _rel_path(md_file)
        stem = md_file.stem.lower()
        rel_lower = rel.lower()

        # 精确路径匹配（忽略 .md 后缀）
        if rel_lower == target_lower or rel_lower == target_lower + ".md":
            return rel
        # stem 匹配
        if stem == target_lower:
            return rel

    # 按 title 匹配
    for md_file in KNOWLEDGE_DIR.rglob("*.md"):
        if ".git" in md_file.parts:
            continue
        try:
            content = md_file.read_text(encoding="utf-8")
            meta, _ = _parse_frontmatter(content)
            title = meta.get("title", md_file.stem)
            if title.lower() == target_lower:
                return _rel_path(md_file)
        except Exception:
            continue

    return None


def get_backlinks(rel_path: str) -> list[WikiBacklink]:
    """获取所有引用了指定页面的反向链接"""
    backlinks: list[WikiBacklink] = []
    target_stem = Path(rel_path).stem.lower()
    target_rel_lower = rel_path.lower()

    for md_file in KNOWLEDGE_DIR.rglob("*.md"):
        if ".git" in md_file.parts:
            continue
        file_rel = _rel_path(md_file)
        # 跳过自身
        if file_rel.lower() == target_rel_lower:
            continue
        try:
            content = md_file.read_text(encoding="utf-8")
        except Exception:
            continue

        meta, body = _parse_frontmatter(content)
        title = meta.get("title", md_file.stem)

        # 检查是否包含指向目标的 [[wikilink]]
        links = extract_wikilinks(body)
        matched = False
        for link in links:
            link_lower = link.lower().strip()
            if (
                link_lower == target_stem
                or link_lower == target_rel_lower
                or link_lower == target_rel_lower.replace(".md", "")
            ):
                matched = True
                break

        if matched:
            # 提取包含链接的行作为 snippet
            snippet = ""
            for line in body.split("\n"):
                if f"[[{target_stem}]]" in line.lower() or f"[[{rel_path}]]" in line.lower():
                    snippet = line.strip()[:120]
                    break
            if not snippet:
                snippet = body[:100].replace("\n", " ").strip()

            backlinks.append(WikiBacklink(path=file_rel, title=title, snippet=snippet))

    return backlinks


# ── 批量操作 ────────────────────────────────────────────────


def list_all_pages() -> list[str]:
    """列出所有条目的相对路径"""
    pages = []
    for md_file in sorted(KNOWLEDGE_DIR.rglob("*.md")):
        if ".git" not in md_file.parts:
            pages.append(_rel_path(md_file))
    return pages


# ── 标签 ────────────────────────────────────────────────────


def get_all_tags() -> list[TagInfo]:
    """获取所有标签及其关联页面，按 count 降序"""
    tag_map: dict[str, list[str]] = {}
    for md_file in KNOWLEDGE_DIR.rglob("*.md"):
        if ".git" in md_file.parts:
            continue
        try:
            content = md_file.read_text(encoding="utf-8")
            meta, _ = _parse_frontmatter(content)
            rel = _rel_path(md_file)
            for tag in meta.get("tags", []):
                tag_map.setdefault(tag, []).append(rel)
        except Exception:
            continue

    tags = [TagInfo(tag=t, count=len(ps), pages=ps) for t, ps in tag_map.items()]
    tags.sort(key=lambda t: t.count, reverse=True)
    return tags


# ── 知识图谱 ────────────────────────────────────────────────


def get_link_graph() -> WikiGraph:
    """构建知识图谱数据（节点 + 链接）"""
    nodes: list[GraphNode] = []
    links: list[GraphLink] = []
    seen_targets: set[str] = set()

    # 先收集所有页面信息
    page_map: dict[str, dict] = {}  # path -> {title, tags, category, content}
    for md_file in KNOWLEDGE_DIR.rglob("*.md"):
        if ".git" in md_file.parts:
            continue
        try:
            content = md_file.read_text(encoding="utf-8")
            meta, body = _parse_frontmatter(content)
            rel = _rel_path(md_file)
            parts = rel.replace("\\", "/").split("/")
            category = parts[0] if len(parts) > 1 else ""
            page_map[rel] = {
                "title": meta.get("title", md_file.stem),
                "tags": meta.get("tags", []),
                "category": category,
                "body": body,
            }
        except Exception:
            continue

    # 构建节点
    for path, info in page_map.items():
        nodes.append(GraphNode(
            id=path,
            title=info["title"],
            path=path,
            category=info["category"],
            tags=info["tags"],
        ))

    # 构建链接（从 wikilinks 提取）
    for path, info in page_map.items():
        wikilinks = extract_wikilinks(info["body"])
        for target in wikilinks:
            resolved = resolve_link(target)
            if resolved and resolved in page_map:
                link_key = f"{path}->{resolved}"
                if link_key not in seen_targets:
                    seen_targets.add(link_key)
                    links.append(GraphLink(source=path, target=resolved))

    return WikiGraph(nodes=nodes, links=links)


# ── 词条索引 ────────────────────────────────────────────────


def get_entry_index() -> dict[str, list[EntryIndexItem]]:
    """按首字母分组返回词条索引"""

    index: dict[str, list[EntryIndexItem]] = {}

    for md_file in KNOWLEDGE_DIR.rglob("*.md"):
        if ".git" in md_file.parts:
            continue
        try:
            content = md_file.read_text(encoding="utf-8")
            meta, _ = _parse_frontmatter(content)
            rel = _rel_path(md_file)
            title = meta.get("title", md_file.stem)
            summary = meta.get("summary", "")
            category = meta.get("category", "")
        except Exception:
            continue

        # 确定首字母分组
        first_char = title[0] if title else "#"
        if "一" <= first_char <= "鿿":
            # 中文字符 -> 拼音首字母
            try:
                from pypinyin import lazy_pinyin
                letter = lazy_pinyin(first_char)[0][0].upper()
            except ImportError:
                letter = "#"
        elif first_char.isalpha():
            letter = first_char.upper()
        elif first_char.isdigit():
            letter = "0-9"
        else:
            letter = "#"

        if letter not in index:
            index[letter] = []
        index[letter].append(EntryIndexItem(
            title=title,
            path=rel,
            summary=summary,
            category=category,
        ))

    # 每组内按标题排序
    for letter in index:
        index[letter].sort(key=lambda x: x.title)

    return dict(sorted(index.items()))
