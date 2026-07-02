"""会话存储服务 — SQLite 实现 + Redis 缓存层"""

import json
import logging
from datetime import datetime
from typing import Optional

try:
    from app.core.cache import cache_delete, cache_get, cache_set
    from app.core.config import settings as _platform_settings
    _CACHE_SESSION_TTL = _platform_settings.CACHE_SESSION_TTL
except ImportError:
    from app.wiki_agent.cache import cache_delete, cache_get, cache_set
    from app.wiki_agent.config import settings as _platform_settings
    _CACHE_SESSION_TTL = _platform_settings.CACHE_SESSION_TTL

from app.wiki_agent.database import get_db

logger = logging.getLogger(__name__)


async def create_session(session_id: str, name: str = "新对话") -> dict:
    """创建新会话"""
    db = await get_db()
    try:
        now = datetime.now().isoformat(timespec="seconds")
        await db.execute(
            "INSERT INTO sessions (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (session_id, name, now, now),
        )
        await db.commit()
        result = {"id": session_id, "name": name, "created_at": now, "updated_at": now}

        # Invalidate list cache
        await cache_delete("wiki:sessions:list")

        return result
    finally:
        await db.close()


async def get_session(session_id: str) -> Optional[dict]:
    """获取会话及消息"""
    # Check Redis cache first
    cache_key = f"wiki:session:{session_id}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached

    db = await get_db()
    try:
        db.row_factory = None
        # 获取会话
        cursor = await db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        row = await cursor.fetchone()
        if not row:
            return None

        # 获取消息
        cursor = await db.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        )
        messages = await cursor.fetchall()

        result = {
            "id": row[0],
            "name": row[1],
            "created_at": row[2],
            "updated_at": row[3],
            "messages": [
                {
                    "role": msg[2],
                    "content": msg[3],
                    "wiki_results": json.loads(msg[4]) if msg[4] else None,
                    "extraction": json.loads(msg[5]) if msg[5] else None,
                }
                for msg in messages
            ],
        }

        # Cache the session
        await cache_set(cache_key, result, ttl=_CACHE_SESSION_TTL)
        return result
    finally:
        await db.close()


async def list_sessions() -> list[dict]:
    """列出所有会话摘要"""
    # Check cache first
    cached = await cache_get("wiki:sessions:list")
    if cached is not None:
        return cached

    db = await get_db()
    try:
        db.row_factory = None
        cursor = await db.execute("SELECT id, name, created_at, updated_at FROM sessions ORDER BY updated_at DESC")
        rows = await cursor.fetchall()

        sessions = []
        for row in rows:
            # 获取消息数量
            count_cursor = await db.execute(
                "SELECT COUNT(*) FROM messages WHERE session_id = ?",
                (row[0],),
            )
            count_row = await count_cursor.fetchone()
            sessions.append(
                {
                    "id": row[0],
                    "name": row[1],
                    "created_at": row[2],
                    "updated_at": row[3],
                    "message_count": count_row[0],
                }
            )

        # Cache with short TTL (60s)
        await cache_set("wiki:sessions:list", sessions, ttl=60)
        return sessions
    finally:
        await db.close()


async def add_message(
    session_id: str,
    role: str,
    content: str,
    wiki_results: Optional[dict] = None,
    extraction: Optional[dict] = None,
) -> int:
    """添加消息"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO messages (session_id, role, content, wiki_results, extraction) VALUES (?, ?, ?, ?, ?)",
            (
                session_id,
                role,
                content,
                json.dumps(wiki_results, ensure_ascii=False) if wiki_results else None,
                json.dumps(extraction, ensure_ascii=False) if extraction else None,
            ),
        )
        # 更新会话的 updated_at
        await db.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(timespec="seconds"), session_id),
        )
        await db.commit()

        # Invalidate related caches
        await cache_delete(f"wiki:session:{session_id}")
        await cache_delete("wiki:sessions:list")

        return cursor.lastrowid
    finally:
        await db.close()


async def update_extraction_status(
    session_id: str,
    thread_id: str,
    status: str,
):
    """更新消息的 extraction 状态（confirmed / rejected）

    Args:
        session_id: 会话 ID
        thread_id: extraction 的 thread_id
        status: "confirmed" 或 "rejected"
    """
    db = await get_db()
    try:
        # 找到包含该 thread_id 的消息
        cursor = await db.execute(
            "SELECT id, extraction FROM messages WHERE session_id = ? AND extraction IS NOT NULL",
            (session_id,),
        )
        rows = await cursor.fetchall()
        for row in rows:
            extraction = json.loads(row[1]) if row[1] else None
            if extraction and extraction.get("thread_id") == thread_id:
                extraction["status"] = status
                await db.execute(
                    "UPDATE messages SET extraction = ? WHERE id = ?",
                    (json.dumps(extraction, ensure_ascii=False), row[0]),
                )
                await db.commit()

                # Invalidate session cache (messages changed)
                await cache_delete(f"wiki:session:{session_id}")
                return
    finally:
        await db.close()


async def update_session_name(session_id: str, name: str):
    """更新会话名称"""
    db = await get_db()
    try:
        await db.execute(
            "UPDATE sessions SET name = ?, updated_at = ? WHERE id = ?",
            (name, datetime.now().isoformat(timespec="seconds"), session_id),
        )
        await db.commit()

        # Invalidate related caches
        await cache_delete(f"wiki:session:{session_id}")
        await cache_delete("wiki:sessions:list")
    finally:
        await db.close()


async def delete_session(session_id: str) -> bool:
    """删除会话及消息"""
    db = await get_db()
    try:
        # 先删除消息
        await db.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        # 再删除会话
        cursor = await db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        await db.commit()

        if cursor.rowcount > 0:
            # Invalidate all related caches
            await cache_delete(f"wiki:session:{session_id}")
            await cache_delete(f"wiki:session:{session_id}:facts")
            await cache_delete("wiki:sessions:list")
            return True
        return False
    finally:
        await db.close()


async def session_exists(session_id: str) -> bool:
    """检查会话是否存在"""
    # Check cache first — if session is cached, it exists
    cached = await cache_get(f"wiki:session:{session_id}")
    if cached is not None:
        return True

    db = await get_db()
    try:
        cursor = await db.execute("SELECT 1 FROM sessions WHERE id = ?", (session_id,))
        row = await cursor.fetchone()
        return row is not None
    finally:
        await db.close()


async def get_session_key_facts(session_id: str) -> list[dict]:
    """获取会话累积的 key_facts（结构化）"""
    cache_key = f"wiki:session:{session_id}:facts"
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached

    db = await get_db()
    try:
        cursor = await db.execute("PRAGMA table_info(sessions)")
        cols = {row[1] for row in await cursor.fetchall()}
        if "key_facts" not in cols:
            return []

        cursor = await db.execute(
            "SELECT key_facts FROM sessions WHERE id = ?",
            (session_id,),
        )
        row = await cursor.fetchone()
        if row and row[0]:
            facts = json.loads(row[0])
            # 兼容旧格式：list[str] → list[dict]
            if facts and isinstance(facts[0], str):
                facts = [{"content": f, "type": "unknown", "confidence": 0.8} for f in facts]
        else:
            facts = []

        await cache_set(cache_key, facts, ttl=_CACHE_SESSION_TTL)
        return facts
    except (json.JSONDecodeError, TypeError):
        return []
    finally:
        await db.close()


async def merge_session_key_facts(session_id: str, new_facts: list[dict]) -> list[dict]:
    """将新 facts 合并到会话的 key_facts 中（去重），返回合并后的完整列表

    Args:
        new_facts: 结构化事实列表，每项格式：
            {"content": "...", "type": "project_context", "confidence": 0.9}
    """
    existing = await get_session_key_facts(session_id)

    existing_contents = {f["content"].strip().lower() for f in existing}
    merged = list(existing)

    for fact in new_facts:
        content = fact.get("content", "").strip() if isinstance(fact, dict) else str(fact).strip()
        if not content:
            continue
        normalized = content.lower()
        if normalized in existing_contents:
            continue

        structured = {
            "content": content,
            "type": fact.get("type", "unknown") if isinstance(fact, dict) else "unknown",
            "confidence": fact.get("confidence", 0.8) if isinstance(fact, dict) else 0.8,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        merged.append(structured)
        existing_contents.add(normalized)

    # 上限 20 条，按置信度排序保留最重要的
    if len(merged) > 20:
        merged.sort(key=lambda f: f.get("confidence", 0), reverse=True)
        merged = merged[:20]

    db = await get_db()
    try:
        cursor = await db.execute("PRAGMA table_info(sessions)")
        cols = {row[1] for row in await cursor.fetchall()}
        if "key_facts" in cols:
            await db.execute(
                "UPDATE sessions SET key_facts = ? WHERE id = ?",
                (json.dumps(merged, ensure_ascii=False), session_id),
            )
            await db.commit()
            await cache_delete(f"wiki:session:{session_id}:facts")
    finally:
        await db.close()

    return merged


# ── User Memory（跨 session 持久记忆）────────────────────────


async def get_user_memory(user_id: str = "default") -> list[dict]:
    """获取用户级持久事实（跨 session 共享）"""
    cache_key = f"wiki:user:{user_id}:memory"
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached

    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT facts FROM user_memory WHERE id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        if row and row[0]:
            facts = json.loads(row[0])
        else:
            facts = []

        await cache_set(cache_key, facts, ttl=_CACHE_SESSION_TTL)
        return facts
    except (json.JSONDecodeError, TypeError):
        return []
    finally:
        await db.close()


async def merge_user_memory(new_facts: list[dict], user_id: str = "default") -> list[dict]:
    """将新 facts 合并到 User Memory。

    Args:
        new_facts: 结构化事实列表，每项格式：
            {"content": "...", "type": "user_preference", "confidence": 0.9}
        user_id: 用户标识

    Returns:
        合并后的完整 facts 列表
    """
    existing = await get_user_memory(user_id)

    # 去重：基于 content 的小写比较
    existing_contents = {f["content"].strip().lower() for f in existing}
    merged = list(existing)

    for fact in new_facts:
        content = fact.get("content", "").strip()
        if not content:
            continue
        normalized = content.lower()

        # 跳过已存在的事实
        if normalized in existing_contents:
            continue

        # 结构化 fact
        structured = {
            "content": content,
            "type": fact.get("type", "unknown"),
            "confidence": fact.get("confidence", 0.8),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        merged.append(structured)
        existing_contents.add(normalized)

    # 上限 30 条，按置信度排序保留最重要的
    if len(merged) > 30:
        merged.sort(key=lambda f: f.get("confidence", 0), reverse=True)
        merged = merged[:30]

    # 持久化
    db = await get_db()
    try:
        now = datetime.now().isoformat(timespec="seconds")
        await db.execute(
            "INSERT INTO user_memory (id, facts, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET facts = ?, updated_at = ?",
            (user_id, json.dumps(merged, ensure_ascii=False), now,
             json.dumps(merged, ensure_ascii=False), now),
        )
        await db.commit()

        await cache_delete(f"wiki:user:{user_id}:memory")
    finally:
        await db.close()

    return merged


async def get_active_eval_task_id(session_id: str) -> str | None:
    """获取会话当前活跃的评估 task_id"""
    db = await get_db()
    try:
        cursor = await db.execute("PRAGMA table_info(sessions)")
        cols = {row[1] for row in await cursor.fetchall()}
        if "active_eval_task_id" not in cols:
            return None

        cursor = await db.execute(
            "SELECT active_eval_task_id FROM sessions WHERE id = ?",
            (session_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row and row[0] else None
    finally:
        await db.close()


async def set_active_eval_task_id(session_id: str, task_id: str | None) -> None:
    """设置会话当前活跃的评估 task_id"""
    db = await get_db()
    try:
        cursor = await db.execute("PRAGMA table_info(sessions)")
        cols = {row[1] for row in await cursor.fetchall()}
        if "active_eval_task_id" in cols:
            await db.execute(
                "UPDATE sessions SET active_eval_task_id = ? WHERE id = ?",
                (task_id, session_id),
            )
            await db.commit()
    finally:
        await db.close()
