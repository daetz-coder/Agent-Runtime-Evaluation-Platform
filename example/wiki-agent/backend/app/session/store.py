"""会话存储服务 — SQLite 实现"""

import json
from datetime import datetime
from typing import Optional

from app.database import get_db


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
        return {"id": session_id, "name": name, "created_at": now, "updated_at": now}
    finally:
        await db.close()


async def get_session(session_id: str) -> Optional[dict]:
    """获取会话及消息"""
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

        return {
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
    finally:
        await db.close()


async def list_sessions() -> list[dict]:
    """列出所有会话摘要"""
    db = await get_db()
    try:
        db.row_factory = None
        cursor = await db.execute(
            "SELECT id, name, created_at, updated_at FROM sessions ORDER BY updated_at DESC"
        )
        rows = await cursor.fetchall()

        sessions = []
        for row in rows:
            # 获取消息数量
            count_cursor = await db.execute(
                "SELECT COUNT(*) FROM messages WHERE session_id = ?",
                (row[0],),
            )
            count_row = await count_cursor.fetchone()
            sessions.append({
                "id": row[0],
                "name": row[1],
                "created_at": row[2],
                "updated_at": row[3],
                "message_count": count_row[0],
            })
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
        return cursor.rowcount > 0
    finally:
        await db.close()


async def session_exists(session_id: str) -> bool:
    """检查会话是否存在"""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT 1 FROM sessions WHERE id = ?", (session_id,))
        row = await cursor.fetchone()
        return row is not None
    finally:
        await db.close()


async def get_session_key_facts(session_id: str) -> list[str]:
    """获取会话累积的 key_facts"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT key_facts FROM sessions WHERE id = ?", (session_id,),
        )
        row = await cursor.fetchone()
        if row and row[0]:
            return json.loads(row[0])
        return []
    except (json.JSONDecodeError, TypeError):
        return []
    finally:
        await db.close()


async def merge_session_key_facts(session_id: str, new_facts: list[str]) -> list[str]:
    """将新 facts 合并到会话的 key_facts 中（去重），返回合并后的完整列表"""
    existing = await get_session_key_facts(session_id)

    # 去重（大小写不敏感 + 去除前后空格）
    seen = {f.strip().lower() for f in existing}
    merged = list(existing)
    for fact in new_facts:
        normalized = fact.strip().lower()
        if normalized and normalized not in seen:
            merged.append(fact.strip())
            seen.add(normalized)

    # 上限 20 条，保留最新的
    if len(merged) > 20:
        merged = merged[-20:]

    # 写回
    db = await get_db()
    try:
        await db.execute(
            "UPDATE sessions SET key_facts = ? WHERE id = ?",
            (json.dumps(merged, ensure_ascii=False), session_id),
        )
        await db.commit()
    finally:
        await db.close()

    return merged


async def get_active_eval_task_id(session_id: str) -> str | None:
    """获取会话当前活跃的评估 task_id"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT active_eval_task_id FROM sessions WHERE id = ?",
            (session_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row and row[0] else None
    finally:
        await db.close()


async def set_active_eval_task_id(session_id: str, task_id: str | None) -> None:
    """设置会话当前活跃的评估 task_id（None 表示结束）"""
    db = await get_db()
    try:
        await db.execute(
            "UPDATE sessions SET active_eval_task_id = ? WHERE id = ?",
            (task_id, session_id),
        )
        await db.commit()
    finally:
        await db.close()
