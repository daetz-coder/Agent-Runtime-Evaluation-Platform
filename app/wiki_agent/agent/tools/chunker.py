"""文档加载与分块 — 支持 PDF / Word / Markdown / TXT 的多格式解析与 RecursiveCharacterTextSplitter 分块。"""

from __future__ import annotations

from pathlib import Path
from typing import List


def load_document(file_path: str | Path) -> str:
    """根据文件扩展名自动选择解析器，返回纯文本。"""
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        return _load_pdf(file_path)
    elif suffix in (".docx", ".doc"):
        return _load_docx(file_path)
    elif suffix in (".md", ".markdown", ".txt", ".rst"):
        return file_path.read_text(encoding="utf-8", errors="replace")
    else:
        raise ValueError(f"不支持的文件格式: {suffix}")


def _load_pdf(file_path: Path) -> str:
    """加载 PDF（需要 pypdf）。"""
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(file_path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except ImportError:
        raise ImportError("PDF 支持需要 pypdf: pip install pypdf")


def _load_docx(file_path: Path) -> str:
    """加载 Word 文档（需要 python-docx）。"""
    try:
        from docx import Document
        doc = Document(str(file_path))
        return "\n".join(p.text for p in doc.paragraphs)
    except ImportError:
        raise ImportError("Word 支持需要 python-docx: pip install python-docx")


def chunk_markdown(
    content: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> list[str]:
    """使用 LangChain RecursiveCharacterTextSplitter 分块。

    分层分隔符: 双换行 → 单换行 → 句号 → 中文标点 → 空格
    比手写实现更稳健，处理边界情况更好。
    """
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", "。", "！", "？", "；", "，", ". ", "! ", "? ", "; ", ", ", " ", ""],
            keep_separator=True,
        )
        return splitter.split_text(content)
    except ImportError:
        # Fallback: simple paragraph-based chunking
        return _fallback_chunk(content, chunk_size, chunk_overlap)


def _fallback_chunk(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """兜底分块器 — 不依赖 langchain。"""
    if not text or len(text) <= chunk_size:
        return [text] if text else []

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - chunk_overlap if end < len(text) else len(text)
    return chunks
