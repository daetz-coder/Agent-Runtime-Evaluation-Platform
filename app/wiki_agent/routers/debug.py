"""Debug / System Inspector — 内部状态可视化 API

提供 Session、Checkpoint、BM25 等内部数据的检查接口。
（平台集成版本，使用 app.wiki_agent 路径）
"""

from __future__ import annotations

import json
import os
import pickle
from collections import Counter

import aiosqlite
from fastapi import APIRouter, HTTPException

from app.wiki_agent.config import settings
from app.wiki_agent.database import get_db

router = APIRouter(prefix="/api/debug", tags=["debug"])

_CHECKPOINT_DB = os.path.join(os.path.dirname(settings.DB_PATH), "checkpoints.db")
_BM25_PATH = settings.BM25_INDEX_PATH


@router.get("/overview")
async def get_overview():
    """各数据源汇总统计"""
    result = {
        "sessions": 0,
        "messages": 0,
        "checkpoints": 0,
        "bm25_docs": 0,
        "vectors": 0,
    }

    try:
        db = await get_db()
        cursor = await db.execute("SELECT COUNT(*) FROM sessions")
        result["sessions"] = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT COUNT(*) FROM messages")
        result["messages"] = (await cursor.fetchone())[0]
        await db.close()
    except Exception:
        pass

    try:
        async with aiosqlite.connect(_CHECKPOINT_DB) as db:
            cursor = await db.execute("SELECT COUNT(DISTINCT thread_id) FROM checkpoints")
            result["checkpoints"] = (await cursor.fetchone())[0]
    except Exception:
        pass

    try:
        with open(_BM25_PATH, "rb") as f:
            data = pickle.load(f)
        result["bm25_docs"] = len(data.get("chunk_meta", []))
    except Exception:
        pass

    try:
        from app.wiki_agent.agent.tools.vector_store import MilvusVectorStore

        result["vectors"] = MilvusVectorStore().count()
    except Exception:
        pass

    return result


@router.get("/sessions")
async def list_sessions():
    """所有 session 列表"""
    db = await get_db()
    try:
        cursor = await db.execute("PRAGMA table_info(sessions)")
        cols = {row[1] for row in await cursor.fetchall()}
        has_key_facts = "key_facts" in cols

        select_parts = ["s.id", "s.name", "s.created_at", "s.updated_at"]
        if has_key_facts:
            select_parts.append("s.key_facts")
        select_parts.append("(SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id) as msg_count")

        cursor = await db.execute(f"SELECT {', '.join(select_parts)} FROM sessions s ORDER BY s.updated_at DESC")
        rows = await cursor.fetchall()
        sessions = []
        for row in rows:
            idx = 4
            key_facts = []
            if has_key_facts:
                try:
                    key_facts = json.loads(row[idx]) if row[idx] else []
                except (json.JSONDecodeError, TypeError):
                    key_facts = []
                idx += 1

            sessions.append(
                {
                    "id": row[0],
                    "name": row[1],
                    "created_at": row[2],
                    "updated_at": row[3],
                    "key_facts": key_facts,
                    "message_count": row[idx],
                }
            )
        return sessions
    finally:
        await db.close()


@router.get("/sessions/{session_id}")
async def get_session_detail(session_id: str):
    """单个 session 详情"""
    db = await get_db()
    try:
        cursor = await db.execute("PRAGMA table_info(sessions)")
        cols = {row[1] for row in await cursor.fetchall()}
        has_key_facts = "key_facts" in cols

        select_parts = ["id", "name", "created_at", "updated_at"]
        if has_key_facts:
            select_parts.append("key_facts")

        cursor = await db.execute(
            f"SELECT {', '.join(select_parts)} FROM sessions WHERE id = ?",
            (session_id,),
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Session not found")

        idx = 4
        key_facts = []
        if has_key_facts:
            try:
                key_facts = json.loads(row[idx]) if row[idx] else []
            except (json.JSONDecodeError, TypeError):
                key_facts = []
            idx += 1

        cursor = await db.execute(
            "SELECT id, role, content, wiki_results, extraction, created_at "
            "FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        )
        msg_rows = await cursor.fetchall()
        messages = []
        for msg in msg_rows:
            wiki_results = extraction = None
            try:
                wiki_results = json.loads(msg[3]) if msg[3] else None
            except Exception:
                pass
            try:
                extraction = json.loads(msg[4]) if msg[4] else None
            except Exception:
                pass
            messages.append(
                {
                    "id": msg[0],
                    "role": msg[1],
                    "content": msg[2],
                    "wiki_results": wiki_results,
                    "extraction": extraction,
                    "created_at": msg[5],
                }
            )
        return {
            "id": row[0],
            "name": row[1],
            "created_at": row[2],
            "updated_at": row[3],
            "key_facts": key_facts,
            "messages": messages,
        }
    finally:
        await db.close()


@router.get("/checkpoints")
async def list_checkpoints():
    """LangGraph checkpoint 线程列表"""
    try:
        async with aiosqlite.connect(_CHECKPOINT_DB) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    thread_id TEXT NOT NULL,
                    checkpoint_ns TEXT NOT NULL DEFAULT '',
                    checkpoint_id TEXT NOT NULL,
                    parent_checkpoint_id TEXT,
                    type TEXT,
                    checkpoint BLOB,
                    metadata BLOB,
                    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
                )
            """)
            await db.commit()
            cursor = await db.execute("""
                SELECT thread_id, COUNT(*) as cnt, MAX(checkpoint_id) as latest
                FROM checkpoints GROUP BY thread_id ORDER BY thread_id
            """)
            rows = await cursor.fetchall()
            threads = []
            for row in rows:
                cursor2 = await db.execute(
                    "SELECT metadata FROM checkpoints WHERE checkpoint_id = ?",
                    (row[2],),
                )
                meta_row = await cursor2.fetchone()
                metadata = None
                if meta_row and meta_row[0]:
                    try:
                        from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

                        metadata = JsonPlusSerializer().loads(meta_row[0])
                    except Exception:
                        metadata = {"raw_size": len(meta_row[0])}
                threads.append(
                    {
                        "thread_id": row[0],
                        "checkpoint_count": row[1],
                        "latest_checkpoint_id": row[2],
                        "metadata": metadata,
                    }
                )
            return threads
    except FileNotFoundError:
        return []


@router.get("/checkpoints/{thread_id}")
async def get_checkpoint_detail(thread_id: str):
    """单个 thread 的 checkpoint 时间线"""
    try:
        from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

        serde = JsonPlusSerializer()

        async with aiosqlite.connect(_CHECKPOINT_DB) as db:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    thread_id TEXT NOT NULL,
                    checkpoint_ns TEXT NOT NULL DEFAULT '',
                    checkpoint_id TEXT NOT NULL,
                    parent_checkpoint_id TEXT,
                    type TEXT,
                    checkpoint BLOB,
                    metadata BLOB,
                    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
                );
                CREATE TABLE IF NOT EXISTS writes (
                    thread_id TEXT NOT NULL,
                    checkpoint_ns TEXT NOT NULL DEFAULT '',
                    checkpoint_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    idx INTEGER NOT NULL,
                    channel TEXT NOT NULL,
                    type TEXT,
                    value BLOB,
                    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
                );
            """)
            cursor = await db.execute(
                "SELECT checkpoint_id, parent_checkpoint_id, type, checkpoint, metadata "
                "FROM checkpoints WHERE thread_id = ? ORDER BY checkpoint_id",
                (thread_id,),
            )
            cp_rows = await cursor.fetchall()
            checkpoints = []
            for cp in cp_rows:
                cp_type = cp[2]
                cp_blob = cp[3]
                meta_blob = cp[4]
                cp_data = _safe_deser_typed(serde, cp_type, cp_blob) if cp_blob else None
                metadata = _safe_deser(serde, meta_blob) if meta_blob else None

                cursor2 = await db.execute(
                    "SELECT channel, type, value FROM writes WHERE thread_id = ? AND checkpoint_id = ?",
                    (thread_id, cp[0]),
                )
                channels = {}
                for w in await cursor2.fetchall():
                    val = _safe_deser_typed(serde, w[1], w[2])
                    channels[w[0]] = _trunc(val)

                checkpoints.append(
                    {
                        "checkpoint_id": cp[0],
                        "parent_checkpoint_id": cp[1],
                        "channels": channels,
                        "metadata": metadata,
                        "checkpoint_summary": _summary(cp_data),
                    }
                )
            return {"thread_id": thread_id, "checkpoints": checkpoints}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Checkpoint DB not found")


@router.get("/bm25")
async def get_bm25_stats():
    """BM25 索引统计"""
    try:
        with open(_BM25_PATH, "rb") as f:
            data = pickle.load(f)
        tokenized = data.get("tokenized_corpus", [])
        meta = data.get("chunk_meta", [])
        all_tokens = [t for toks in tokenized for t in toks]
        freq = Counter(all_tokens)
        paths = Counter(m.get("path", "") for m in meta)
        return {
            "total_docs": len(meta),
            "total_tokens": len(all_tokens),
            "unique_tokens": len(freq),
            "top_tokens": [{"token": t, "count": c} for t, c in freq.most_common(30)],
            "path_distribution": [{"path": p, "chunks": c} for p, c in paths.most_common(50)],
            "chunks": [
                {
                    "path": m.get("path", ""),
                    "title": m.get("title", ""),
                    "snippet": m.get("snippet", "")[:100],
                    "chunk_index": m.get("chunk_index", 0),
                }
                for m in meta[:100]
            ],
        }
    except FileNotFoundError:
        return {"total_docs": 0, "total_tokens": 0, "error": "BM25 index not found"}


def _safe_deser(serde, blob):
    if not blob:
        return None
    try:
        return serde.loads(blob)
    except Exception:
        return {"_error": True, "size": len(blob)}


def _safe_deser_typed(serde, type_str, value_blob):
    """反序列化 writes 表的 (type, value) 元组"""
    if not value_blob:
        return None
    try:
        # loads_typed 接受 (type, value) 元组
        return serde.loads_typed((type_str, value_blob))
    except Exception:
        # 退化为普通 loads
        try:
            return serde.loads(value_blob)
        except Exception:
            return {"_error": True, "type": type_str, "size": len(value_blob)}


def _summary(data):
    if not data or not isinstance(data, dict):
        return None
    cv = data.get("channel_values", {})
    if not cv:
        return {"channels": list(data.keys())[:10]}
    out = {}
    for k, v in cv.items():
        if isinstance(v, str):
            out[k] = v[:200]
        elif isinstance(v, list):
            out[k] = f"[{len(v)} items]"
        elif isinstance(v, dict):
            out[k] = f"{{{len(v)} keys}}"
        else:
            s = str(v) if v is not None else "null"
            out[k] = s[:200]
    return out


def _trunc(val, n=500):
    if val is None:
        return None
    if isinstance(val, str):
        return val[:n] + "..." if len(val) > n else val
    if isinstance(val, (list, dict)):
        s = json.dumps(val, ensure_ascii=False, default=str)
        return s[:n] + "..." if len(s) > n else val
    return val
