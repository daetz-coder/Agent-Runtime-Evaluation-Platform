"""BM25 索引管理 — 基于 jieba 分词 + rank_bm25 的倒排索引"""

from __future__ import annotations

import os
import pickle
from pathlib import Path

import jieba
from rank_bm25 import BM25Okapi

from app.wiki_agent.config import settings

# 停用词（常见无意义词）
_STOPWORDS = frozenset([
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都",
    "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你",
    "会", "着", "没有", "看", "好", "自己", "这", "他", "她", "它",
    "们", "那", "里", "为", "什么", "怎么", "如何", "可以", "以",
    "及", "与", "或", "但", "而", "把", "被", "让", "从", "对",
    "等", "能", "将", "已", "还", "更", "其", "中", "之", "则",
])


def _tokenize(text: str) -> list[str]:
    """中文分词，过滤停用词和单字 token"""
    tokens = jieba.lcut(text)
    return [t for t in tokens if len(t) > 1 and t not in _STOPWORDS]


class BM25Index:
    """BM25 倒排索引，支持增量更新和持久化"""

    def __init__(self):
        self._tokenized_corpus: list[list[str]] = []  # 每个 chunk 的 token 列表
        self._chunk_meta: list[dict] = []              # 每个 chunk 的元数据
        self._bm25: BM25Okapi | None = None
        self._dirty = False  # 是否需要重建 BM25 实例

    def add_document(self, path: str, title: str, chunks: list[str]):
        """添加一个文档的所有 chunks 到索引

        Args:
            path: 文档路径（唯一标识）
            title: 文档标题
            chunks: 该文档的文本块列表
        """
        # 先移除旧数据
        self.remove_document(path)

        for i, chunk in enumerate(chunks):
            # 拼接标题 + chunk 内容用于分词（与 Milvus 一致）
            text = f"{title}\n{chunk}"
            tokens = _tokenize(text)
            self._tokenized_corpus.append(tokens)
            self._chunk_meta.append({
                "path": path,
                "title": title,
                "snippet": chunk[:200],
                "content": chunk,
                "chunk_index": i,
            })

        self._dirty = True

    def remove_document(self, path: str):
        """按文档路径移除所有相关 chunks"""
        indices_to_remove = [
            i for i, meta in enumerate(self._chunk_meta)
            if meta["path"] == path
        ]
        # 从后往前删，避免索引偏移
        for i in reversed(indices_to_remove):
            self._tokenized_corpus.pop(i)
            self._chunk_meta.pop(i)

        if indices_to_remove:
            self._dirty = True

    def search(self, query: str, limit: int = 5) -> list[dict]:
        """BM25 搜索

        Args:
            query: 搜索查询
            limit: 返回结果数量

        Returns:
            list[dict]: 搜索结果，按 path 去重，保留最高分 chunk
        """
        if not self._tokenized_corpus:
            return []

        # 确保 BM25 实例是最新的
        self._rebuild_if_dirty()

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        scores = self._bm25.get_scores(query_tokens)

        # 按 path 去重，保留最高分 chunk
        seen_paths: dict[str, dict] = {}
        for i, score in enumerate(scores):
            if score <= 0:
                continue
            meta = self._chunk_meta[i]
            path = meta["path"]
            if path not in seen_paths or score > seen_paths[path]["score"]:
                seen_paths[path] = {
                    "path": path,
                    "title": meta["title"],
                    "snippet": meta["snippet"],
                    "content": meta.get("content", meta["snippet"]),
                    "score": float(score),
                    "search_type": "bm25",
                }

        # 按分数排序
        results = sorted(seen_paths.values(), key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def save(self):
        """持久化索引到磁盘"""
        index_path = settings.BM25_INDEX_PATH
        os.makedirs(os.path.dirname(index_path), exist_ok=True)
        data = {
            "tokenized_corpus": self._tokenized_corpus,
            "chunk_meta": self._chunk_meta,
        }
        with open(index_path, "wb") as f:
            pickle.dump(data, f)

    def load(self) -> bool:
        """从磁盘加载索引，返回是否成功"""
        index_path = settings.BM25_INDEX_PATH
        if not os.path.exists(index_path):
            return False
        try:
            with open(index_path, "rb") as f:
                data = pickle.load(f)
            self._tokenized_corpus = data["tokenized_corpus"]
            self._chunk_meta = data["chunk_meta"]
            self._dirty = True
            self._rebuild_if_dirty()
            return True
        except Exception as e:
            print(f"[BM25] 索引加载失败: {e}")
            return False

    def build_from_knowledge_dir(self):
        """从 knowledge 目录全量重建索引"""
        from app.wiki_agent.agent.tools.chunker import chunk_markdown
        import re

        knowledge_dir = Path(settings.KNOWLEDGE_DIR)
        if not knowledge_dir.exists():
            return

        self._tokenized_corpus = []
        self._chunk_meta = []
        self._dirty = True

        count = 0
        for md_file in knowledge_dir.rglob("*.md"):
            if ".git" in md_file.parts:
                continue
            try:
                content = md_file.read_text(encoding="utf-8")
            except Exception:
                continue

            # 解析 frontmatter
            title = md_file.stem
            body = content
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    for line in parts[1].split("\n"):
                        if line.strip().startswith("title:"):
                            title = line.split(":", 1)[1].strip().strip('"\'')
                    body = parts[2].strip()

            rel_path = str(md_file.relative_to(knowledge_dir)).replace("\\", "/")
            chunks = chunk_markdown(body, chunk_size=500, chunk_overlap=50)
            if not chunks:
                chunks = [body]

            for i, chunk in enumerate(chunks):
                text = f"{title}\n{chunk}"
                tokens = _tokenize(text)
                self._tokenized_corpus.append(tokens)
                self._chunk_meta.append({
                    "path": rel_path,
                    "title": title,
                    "snippet": chunk[:200],
                    "content": chunk,
                    "chunk_index": i,
                })
            count += 1

        self._rebuild_if_dirty()
        self.save()
        print(f"[BM25] 全量重建完成: {count} 个文档, {len(self._tokenized_corpus)} 个 chunks")

    def _rebuild_if_dirty(self):
        """如果数据有变更，重建 BM25 实例"""
        if self._dirty:
            if self._tokenized_corpus:
                self._bm25 = BM25Okapi(self._tokenized_corpus)
            else:
                self._bm25 = None
            self._dirty = False


# 全局单例
_bm25_index: BM25Index | None = None


def get_bm25_index() -> BM25Index:
    """获取 BM25 索引单例（懒加载，首次访问时加载或重建）"""
    global _bm25_index
    if _bm25_index is None:
        _bm25_index = BM25Index()
        if not _bm25_index.load():
            print("[BM25] 索引文件不存在，从 knowledge 目录全量重建...")
            _bm25_index.build_from_knowledge_dir()
    return _bm25_index
