"""环境监控器 — 感知 knowledge/ 目录文件变化，自动触发索引同步

两种模式：
1. 轮询模式（默认）：定期扫描文件 hash，检测变化
2. 事件模式（可选）：使用 watchdog 实时监控文件系统事件

检测到变化后自动调用 sync_manager 同步 Milvus + BM25。
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable

from app.wiki_agent.config import settings

logger = logging.getLogger(__name__)


class ChangeType(str, Enum):
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"


@dataclass
class FileChangeEvent:
    """文件变化事件"""
    path: str           # 相对路径，如 "guides/setup.md"
    change_type: ChangeType
    old_hash: str | None = None
    new_hash: str | None = None


@dataclass
class FileSnapshot:
    """文件快照"""
    path: str
    hash: str
    mtime: float
    size: int


class EnvironmentMonitor:
    """环境监控器 — 检测 knowledge/ 目录变化

    Usage:
        monitor = EnvironmentMonitor()
        monitor.on_change(handle_change)  # 注册回调
        await monitor.start()             # 启动监控
    """

    def __init__(self, poll_interval: float = 5.0):
        self._knowledge_dir = Path(settings.KNOWLEDGE_DIR)
        self._poll_interval = poll_interval
        self._snapshots: dict[str, FileSnapshot] = {}
        self._callbacks: list[Callable[[list[FileChangeEvent]], None]] = []
        self._running = False
        self._task: asyncio.Task | None = None

    def on_change(self, callback: Callable[[list[FileChangeEvent]], None]):
        """注册变化回调"""
        self._callbacks.append(callback)

    async def start(self):
        """启动监控（轮询模式）"""
        if self._running:
            return

        self._running = True
        # 初始快照
        self._snapshots = self._scan_all()
        logger.info(f"[EnvMonitor] 启动监控: {self._knowledge_dir} ({len(self._snapshots)} 文件)")

        # 启动轮询
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self):
        """停止监控"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("[EnvMonitor] 已停止监控")

    async def check_now(self) -> list[FileChangeEvent]:
        """立即检查一次变化（手动触发）"""
        return await self._detect_changes()

    def _scan_all(self) -> dict[str, FileSnapshot]:
        """扫描所有文件，生成快照"""
        snapshots = {}
        if not self._knowledge_dir.exists():
            return snapshots

        for md_file in self._knowledge_dir.rglob("*.md"):
            if ".git" in md_file.parts:
                continue
            rel_path = str(md_file.relative_to(self._knowledge_dir)).replace("\\", "/")
            try:
                stat = md_file.stat()
                content = md_file.read_bytes()
                file_hash = hashlib.md5(content).hexdigest()
                snapshots[rel_path] = FileSnapshot(
                    path=rel_path,
                    hash=file_hash,
                    mtime=stat.st_mtime,
                    size=stat.st_size,
                )
            except Exception as e:
                logger.warning(f"[EnvMonitor] 读取文件失败 {md_file}: {e}")

        return snapshots

    async def _poll_loop(self):
        """轮询循环"""
        while self._running:
            try:
                await asyncio.sleep(self._poll_interval)
                changes = await self._detect_changes()
                if changes:
                    await self._notify_callbacks(changes)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[EnvMonitor] 轮询异常: {e}")

    async def _detect_changes(self) -> list[FileChangeEvent]:
        """检测文件变化"""
        current = self._scan_all()
        changes: list[FileChangeEvent] = []

        # 检测新增和修改
        for path, snapshot in current.items():
            if path not in self._snapshots:
                changes.append(FileChangeEvent(
                    path=path,
                    change_type=ChangeType.CREATED,
                    new_hash=snapshot.hash,
                ))
            elif snapshot.hash != self._snapshots[path].hash:
                changes.append(FileChangeEvent(
                    path=path,
                    change_type=ChangeType.MODIFIED,
                    old_hash=self._snapshots[path].hash,
                    new_hash=snapshot.hash,
                ))

        # 检测删除
        for path in self._snapshots:
            if path not in current:
                changes.append(FileChangeEvent(
                    path=path,
                    change_type=ChangeType.DELETED,
                    old_hash=self._snapshots[path].hash,
                ))

        # 更新快照
        self._snapshots = current
        return changes

    async def _notify_callbacks(self, changes: list[FileChangeEvent]):
        """通知所有回调"""
        for change in changes:
            logger.info(f"[EnvMonitor] 检测到变化: {change.change_type.value} {change.path}")

        for callback in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(changes)
                else:
                    callback(changes)
            except Exception as e:
                logger.error(f"[EnvMonitor] 回调执行失败: {e}")


# ── 默认回调：自动同步 ──────────────────────────────────────

async def auto_sync_callback(changes: list[FileChangeEvent]):
    """默认回调：检测到变化时自动同步索引"""
    from app.wiki_agent.agent.tools.sync_manager import sync_manager

    for change in changes:
        try:
            if change.change_type == ChangeType.DELETED:
                sync_manager._delete_from_vector_store(change.path)
                logger.info(f"[EnvMonitor] 已清理索引: {change.path}")
            else:
                sync_manager.reindex_page(change.path)
                logger.info(f"[EnvMonitor] 已同步索引: {change.path}")
        except Exception as e:
            logger.error(f"[EnvMonitor] 同步失败 {change.path}: {e}")


# ── 全局实例 ─────────────────────────────────────────────────

_monitor: EnvironmentMonitor | None = None


def get_env_monitor() -> EnvironmentMonitor:
    """获取全局环境监控器实例"""
    global _monitor
    if _monitor is None:
        _monitor = EnvironmentMonitor(poll_interval=5.0)
        _monitor.on_change(auto_sync_callback)
    return _monitor
