"""WikiSyncManager — Wiki 数据库同步管理器

确保 Markdown、Milvus、BM25、Git 四端一致。
所有写操作（REST API、Agent CRUD）应经此模块。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.wiki_agent.agent.tools.bm25_index import get_bm25_index
from app.wiki_agent.agent.tools.chunker import chunk_markdown
from app.wiki_agent.agent.tools.vector_store import ChunkRecord, get_vector_store
from app.wiki_agent.config import settings
from app.wiki_agent.wiki import git_service, service
from app.wiki_agent.wiki.schemas import WikiPageCreate, WikiPageUpdate


class WikiSyncManager:
    """Wiki 数据库同步管理器"""

    def __init__(self) -> None:
        self._embedding_model = None

    @property
    def vector_store(self):
        """延迟初始化 Milvus vector store"""
        return get_vector_store()

    @property
    def embedding_model(self):
        """延迟加载并缓存 Embedding 模型"""
        if self._embedding_model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL_PATH)
                print("[WikiSync] Embedding 模型已加载")
            except Exception as e:
                print(f"[WikiSync] Embedding 模型加载失败: {e}")
        return self._embedding_model

    def create(
        self,
        path: str,
        title: str,
        content: str,
        tags: list[str] | None = None,
        source: str = "agent",
        git_message: str | None = None,
    ) -> dict:
        """创建知识条目

        流程:
        1. 写入 Markdown 文件
        2. 生成 embedding 并存入 Milvus
        3. Git 提交

        Args:
            path: 知识条目路径
            title: 条目标题
            content: Markdown 内容
            tags: 标签列表
            source: 来源

        Returns:
            dict: 创建结果
        """
        try:
            page = service.create_page(
                path,
                WikiPageCreate(
                    title=title,
                    content=content,
                    tags=tags or [],
                    source=source,
                ),
            )

            self._sync_to_vector_store(path, title, content, tags or [])

            git_service.commit_changes(
                git_message or f"创建知识: {title}",
                files=[path],
            )

            return {
                "status": "ok",
                "action": "create",
                "path": path,
                "message": f"已创建: {page.title}",
            }
        except FileExistsError:
            return {
                "status": "error",
                "message": f"条目已存在: {path}",
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"创建失败: {str(e)}",
            }

    def update(
        self,
        path: str,
        title: str | None = None,
        content: str | None = None,
        tags: list[str] | None = None,
        links: list[str] | None = None,
        git_message: str | None = None,
    ) -> dict:
        """更新知识条目

        流程:
        1. 更新 Markdown 文件
        2. 更新 Milvus 向量索引
        3. Git 提交

        Args:
            path: 知识条目路径
            title: 新标题（可选）
            content: 新内容（可选）
            tags: 新标签（可选）

        Returns:
            dict: 更新结果
        """
        try:
            page = service.update_page(
                path,
                WikiPageUpdate(
                    title=title,
                    content=content,
                    tags=tags,
                    links=links,
                ),
            )

            updated_content = content or page.content
            updated_title = title or page.title
            updated_tags = tags or page.tags
            self._sync_to_vector_store(path, updated_title, updated_content, updated_tags)

            git_service.commit_changes(
                git_message or f"更新知识: {page.title}",
                files=[path],
            )

            return {
                "status": "ok",
                "action": "update",
                "path": path,
                "message": f"已更新: {page.title}",
            }
        except FileNotFoundError:
            return {
                "status": "error",
                "message": f"条目不存在: {path}",
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"更新失败: {str(e)}",
            }

    def delete(self, path: str, git_message: str | None = None) -> dict:
        """删除知识条目

        流程:
        1. 删除 Markdown 文件
        2. 删除 Milvus 向量
        3. Git 提交

        Args:
            path: 知识条目路径

        Returns:
            dict: 删除结果
        """
        try:
            service.delete_page(path)
            self._delete_from_vector_store(path)

            git_service.commit_changes(
                git_message or f"删除知识: {path}",
                files=[path],
            )

            return {
                "status": "ok",
                "action": "delete",
                "path": path,
                "message": f"已删除: {path}",
            }
        except FileNotFoundError:
            return {
                "status": "error",
                "message": f"条目不存在: {path}",
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"删除失败: {str(e)}",
            }

    def reindex_all(self) -> dict:
        """遍历 knowledge/ 目录所有 Markdown，全量重建 Milvus + BM25。"""
        from pathlib import Path
        from app.wiki_agent.agent.tools.chunker import chunk_markdown

        knowledge_dir = Path(settings.KNOWLEDGE_DIR)
        if not knowledge_dir.exists():
            return {"status": "error", "message": "Knowledge 目录不存在"}

        count = 0
        for md_file in knowledge_dir.rglob("*.md"):
            if ".git" in md_file.parts:
                continue
            try:
                content = md_file.read_text(encoding="utf-8")
                title = md_file.stem
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        for line in parts[1].split("\n"):
                            if line.strip().startswith("title:"):
                                title = line.split(":", 1)[1].strip().strip("\"'")
                        content = parts[2].strip()
                rel_path = str(md_file.relative_to(knowledge_dir)).replace("\\", "/")
                self._sync_to_vector_store(rel_path, title, content, [])
                count += 1
            except Exception as e:
                print(f"[Sync] 重建失败 {md_file}: {e}")

        bm25 = get_bm25_index()
        bm25.save()
        return {"status": "ok", "reindexed": count}
        """根据磁盘上的 Markdown 重建 Milvus + BM25 索引（用于 Git 回滚等）"""
        try:
            page = service.get_page(path)
            self._sync_to_vector_store(path, page.title, page.content, page.tags or [])
            return {"status": "ok", "path": path, "message": f"已重建索引: {page.title}"}
        except FileNotFoundError:
            self._delete_from_vector_store(path)
            return {"status": "ok", "path": path, "message": f"条目已删除，已清理索引: {path}"}
        except Exception as e:
            return {"status": "error", "message": f"索引同步失败: {str(e)}"}

    def rollback(self, path: str, commit_hash: str) -> dict:
        """Git 回滚文件内容，并同步 Milvus + BM25"""
        ok = git_service.rollback(path, commit_hash)
        if not ok:
            return {"status": "error", "message": "回滚失败"}
        return self.reindex_page(path)

    def import_markdown(
        self,
        path: str,
        content: str,
        source: str = "import",
        overwrite: bool = False,
    ) -> dict:
        """导入 Markdown（创建或覆盖）"""
        if overwrite:
            return self.update(
                path,
                content=content,
                git_message=f"导入覆盖: {path} (来源: {source})",
            )
        title = path.rsplit("/", 1)[-1].replace(".md", "")
        if content.startswith("# "):
            title = content.split("\n")[0][2:].strip()
        return self.create(
            path,
            title=title,
            content=content,
            source=source,
            git_message=f"导入条目: {title} (来源: {source})",
        )

    def _sync_to_vector_store(
        self,
        path: str,
        title: str,
        content: str,
        tags: list[str],
    ) -> None:
        """同步到 Milvus（带分块）

        Args:
            path: 知识条目路径
            title: 条目标题
            content: 条目内容
            tags: 标签列表
        """
        store = self.vector_store
        if not store.available:
            print("[WikiSync] Milvus 不可用，跳过向量同步")
            return

        try:
            store.delete_by_path(path)

            chunks = chunk_markdown(content, chunk_size=500, chunk_overlap=50)
            if not chunks:
                chunks = [content]

            updated_at = datetime.now().isoformat()
            records: list[ChunkRecord] = []
            for i, chunk in enumerate(chunks):
                records.append(
                    ChunkRecord(
                        chunk_id=f"{path}#chunk{i}",
                        vector=self._generate_embedding(f"{title}\n{chunk}"),
                        path=path,
                        title=title,
                        document=chunk,
                        tags=",".join(tags),
                        chunk_index=i,
                        total_chunks=len(chunks),
                        updated_at=updated_at,
                    )
                )

            store.insert_chunks(records)
            print(f"[WikiSync] Milvus 已同步: {path} ({len(chunks)} 块)")

            bm25 = get_bm25_index()
            bm25.add_document(path, title, chunks)
            bm25.save()
            print(f"[WikiSync] BM25 已同步: {path} ({len(chunks)} 块)")
        except Exception as e:
            print(f"[WikiSync] Milvus 同步失败: {e}")

    def _delete_from_vector_store(self, path: str) -> None:
        """从 Milvus 和 BM25 删除（包括所有分块）

        Args:
            path: 知识条目路径
        """
        deleted = self.vector_store.delete_by_path(path)
        if deleted:
            print(f"[WikiSync] 已删除旧分块: {deleted} 个")

        bm25 = get_bm25_index()
        bm25.remove_document(path)
        bm25.save()
        print(f"[WikiSync] BM25 已删除: {path}")

    def _generate_embedding(self, text: str) -> list[float]:
        """生成文本的向量嵌入

        Args:
            text: 输入文本

        Returns:
            list[float]: 向量嵌入
        """
        model = self.embedding_model
        if model is None:
            return [0.0] * settings.EMBEDDING_DIM
        try:
            embedding = model.encode(text)
            return embedding.tolist()
        except Exception as e:
            print(f"[WikiSync] Embedding 生成失败: {e}")
            return [0.0] * settings.EMBEDDING_DIM


# 全局实例
sync_manager = WikiSyncManager()
