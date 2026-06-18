"""文本分块工具 — 将长文档拆分为小块用于向量检索"""

from __future__ import annotations


def chunk_text(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> list[str]:
    """将文本分块

    Args:
        text: 原始文本
        chunk_size: 每块的目标大小（字符数）
        chunk_overlap: 块之间的重叠大小

    Returns:
        list[str]: 分块后的文本列表
    """
    if not text or len(text) <= chunk_size:
        return [text] if text else []

    chunks = []
    start = 0

    while start < len(text):
        # 计算结束位置
        end = start + chunk_size

        # 如果不是最后一块，尝试在句子边界分割
        if end < len(text):
            # 查找最近的句子结束符
            boundary = _find_sentence_boundary(text, end)
            if boundary > start:
                end = boundary

        # 提取块
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # 下一块的起始位置（考虑重叠）
        start = end - chunk_overlap if end < len(text) else len(text)

    return chunks


def _find_sentence_boundary(text: str, target_pos: int) -> int:
    """在目标位置附近查找句子边界

    优先级：句号 > 换行 > 逗号 > 空格
    """
    # 在目标位置前后 100 字符范围内查找
    search_range = 100
    start = max(0, target_pos - search_range)
    end = min(len(text), target_pos + search_range)

    # 句子结束符（按优先级）
    delimiters = ['。', '！', '？', '\n', '；', '，', '.', '!', '?', ';', ',']

    best_pos = target_pos
    best_priority = len(delimiters)

    for i, delim in enumerate(delimiters):
        # 向前查找
        pos = text.rfind(delim, start, target_pos)
        if pos != -1 and i < best_priority:
            best_pos = pos + 1
            best_priority = i
            break

        # 向后查找
        pos = text.find(delim, target_pos, end)
        if pos != -1 and i < best_priority:
            best_pos = pos + 1
            best_priority = i
            break

    return best_pos


def chunk_markdown(
    content: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> list[str]:
    """Markdown 专用分块 — 保持标题结构

    Args:
        content: Markdown 内容
        chunk_size: 每块的目标大小
        chunk_overlap: 块之间的重叠大小

    Returns:
        list[str]: 分块后的文本列表
    """
    if not content:
        return []

    # 按标题分割
    sections = _split_by_headers(content)

    # 如果只有一个部分，直接分块
    if len(sections) <= 1:
        return chunk_text(content, chunk_size, chunk_overlap)

    # 对每个部分分别分块
    chunks = []
    for header, body in sections:
        if not body.strip():
            continue

        # 将标题添加到第一块
        section_chunks = chunk_text(body, chunk_size - len(header), chunk_overlap)
        if section_chunks:
            # 第一块加上标题
            first_chunk = f"{header}\n{section_chunks[0]}" if header else section_chunks[0]
            chunks.append(first_chunk)
            chunks.extend(section_chunks[1:])
        elif header:
            chunks.append(header)

    return chunks


def _split_by_headers(content: str) -> list[tuple[str, str]]:
    """按 Markdown 标题分割内容

    Returns:
        list[tuple[str, str]]: (标题, 内容) 列表
    """
    import re

    sections = []
    current_header = ""
    current_body = []

    for line in content.split('\n'):
        if re.match(r'^#{1,6}\s+', line):
            # 保存上一个部分
            if current_body:
                sections.append((current_header, '\n'.join(current_body)))
            # 开始新部分
            current_header = line
            current_body = []
        else:
            current_body.append(line)

    # 保存最后一个部分
    if current_body:
        sections.append((current_header, '\n'.join(current_body)))

    return sections
