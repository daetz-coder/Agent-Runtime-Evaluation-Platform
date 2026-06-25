"""Debug / System Inspector — 内部状态可视化 API

提供 Session、Checkpoint、BM25 等内部数据的检查接口。
"""

from __future__ import annotations

import json
import os
import pickle
from collections import Counter
from pathlib import Path

import aiosqlite
from fastapi import APIRouter, HTTPException

from app.config import settings
from app.database import get_db

router = APIRouter(prefix="/api/debug", tags=["debug"])

_CHECKPOINT_DB = os.path.join(os.path.dirname(settings.DB_PATH), "checkpoints.db")
_BM25_PATH = settings.BM25_INDEX_PATH


# ── Overview ────────────────────────────────────────────────


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

    # Sessions + Messages
    try:
        db = await get_db()
        cursor = await db.execute("SELECT COUNT(*) FROM sessions")
        result["sessions"] = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT COUNT(*) FROM messages")
        result["messages"] = (await cursor.fetchone())[0]
        await db.close()
    except Exception:
        pass

    # Checkpoints
    try:
        async with aiosqlite.connect(_CHECKPOINT_DB) as db:
            cursor = await db.execute("SELECT COUNT(DISTINCT thread_id) FROM checkpoints")
            result["checkpoints"] = (await cursor.fetchone())[0]
    except Exception:
        pass

    # BM25
    try:
        with open(_BM25_PATH, "rb") as f:
            data = pickle.load(f)
        result["bm25_docs"] = len(data.get("chunk_meta", []))
    except Exception:
        pass

    # Vectors (ChromaDB)
    try:
        from app.agent.tools.sync_manager import sync_manager
        col = sync_manager.chroma_collection
        if col is not None:
            result["vectors"] = col.count()
    except Exception:
        pass

    return result


# ── Sessions ────────────────────────────────────────────────


@router.get("/sessions")
async def list_sessions():
    """所有 session 列表（含 key_facts、消息数）"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT s.id, s.name, s.created_at, s.updated_at, "
            "s.key_facts, s.active_eval_task_id, "
            "(SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id) as msg_count "
            "FROM sessions s ORDER BY s.updated_at DESC"
        )
        rows = await cursor.fetchall()

        sessions = []
        for row in rows:
            key_facts_raw = row[4] if len(row) > 4 else None
            try:
                key_facts = json.loads(key_facts_raw) if key_facts_raw else []
            except (json.JSONDecodeError, TypeError):
                key_facts = []

            active_task = row[5] if len(row) > 5 else None

            sessions.append({
                "id": row[0],
                "name": row[1],
                "created_at": row[2],
                "updated_at": row[3],
                "key_facts": key_facts,
                "active_eval_task_id": active_task,
                "message_count": row[6],
            })
        return sessions
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await db.close()


@router.get("/sessions/{session_id}")
async def get_session_detail(session_id: str):
    """单个 session 详情：消息列表 + key_facts"""
    db = await get_db()
    try:
        # Session 信息
        cursor = await db.execute(
            "SELECT id, name, created_at, updated_at, key_facts, active_eval_task_id "
            "FROM sessions WHERE id = ?",
            (session_id,),
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Session not found")

        key_facts_raw = row[4] if len(row) > 4 else None
        try:
            key_facts = json.loads(key_facts_raw) if key_facts_raw else []
        except (json.JSONDecodeError, TypeError):
            key_facts = []

        # 消息列表
        cursor = await db.execute(
            "SELECT id, role, content, wiki_results, extraction, created_at "
            "FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        )
        msg_rows = await cursor.fetchall()

        messages = []
        for msg in msg_rows:
            wiki_results = None
            extraction = None
            try:
                wiki_results = json.loads(msg[3]) if msg[3] else None
            except (json.JSONDecodeError, TypeError):
                pass
            try:
                extraction = json.loads(msg[4]) if msg[4] else None
            except (json.JSONDecodeError, TypeError):
                pass

            messages.append({
                "id": msg[0],
                "role": msg[1],
                "content": msg[2],
                "wiki_results": wiki_results,
                "extraction": extraction,
                "created_at": msg[5],
            })

        return {
            "id": row[0],
            "name": row[1],
            "created_at": row[2],
            "updated_at": row[3],
            "key_facts": key_facts,
            "active_eval_task_id": row[5] if len(row) > 5 else None,
            "messages": messages,
        }
    finally:
        await db.close()


# ── Checkpoints (LangGraph) ─────────────────────────────────


@router.get("/checkpoints")
async def list_checkpoints():
    """LangGraph checkpoint 线程列表"""
    try:
        async with aiosqlite.connect(_CHECKPOINT_DB) as db:
            # 每个 thread 的 checkpoint 数量 + 最新 checkpoint
            cursor = await db.execute("""
                SELECT
                    thread_id,
                    COUNT(*) as checkpoint_count,
                    MAX(checkpoint_id) as latest_checkpoint_id
                FROM checkpoints
                GROUP BY thread_id
                ORDER BY thread_id
            """)
            rows = await cursor.fetchall()

            threads = []
            for row in rows:
                # 获取最新 checkpoint 的 metadata
                cursor2 = await db.execute(
                    "SELECT metadata, checkpoint FROM checkpoints WHERE checkpoint_id = ?",
                    (row[2],),
                )
                meta_row = await cursor2.fetchone()
                metadata_summary = None
                if meta_row and meta_row[0]:
                    try:
                        from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
                        serde = JsonPlusSerializer()
                        metadata_summary = _safe_deserialize(serde, meta_row[0])
                    except Exception:
                        metadata_summary = {"raw_size": len(meta_row[0]) if meta_row[0] else 0}

                threads.append({
                    "thread_id": row[0],
                    "checkpoint_count": row[1],
                    "latest_checkpoint_id": row[2],
                    "metadata": metadata_summary,
                })

            return threads
    except FileNotFoundError:
        return []
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/checkpoints/{thread_id}")
async def get_checkpoint_detail(thread_id: str):
    """单个 thread 的 checkpoint 时间线 + channel 值"""
    try:
        from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
        serde = JsonPlusSerializer()

        async with aiosqlite.connect(_CHECKPOINT_DB) as db:
            # 所有 checkpoints
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
                checkpoint_data = _safe_deserialize_typed(serde, cp_type, cp_blob) if cp_blob else None
                metadata = _safe_deserialize(serde, meta_blob) if meta_blob else None

                # 获取该 checkpoint 的 writes（channel 值）
                cursor2 = await db.execute(
                    "SELECT channel, type, value FROM writes "
                    "WHERE thread_id = ? AND checkpoint_id = ?",
                    (thread_id, cp[0]),
                )
                write_rows = await cursor2.fetchall()

                channels = {}
                for w in write_rows:
                    channel_name = w[0]
                    channel_value = _safe_deserialize_typed(serde, w[1], w[2]) if w[2] else None
                    # 截断过长的值
                    channels[channel_name] = _truncate_value(channel_value)

                checkpoints.append({
                    "checkpoint_id": cp[0],
                    "parent_checkpoint_id": cp[1],
                    "channels": channels,
                    "metadata": metadata,
                    "checkpoint_summary": _summarize_checkpoint(checkpoint_data),
                })

            return {
                "thread_id": thread_id,
                "checkpoints": checkpoints,
            }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Checkpoint DB not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── BM25 Index ──────────────────────────────────────────────


@router.get("/bm25")
async def get_bm25_stats():
    """BM25 索引统计"""
    try:
        with open(_BM25_PATH, "rb") as f:
            data = pickle.load(f)

        tokenized_corpus = data.get("tokenized_corpus", [])
        chunk_meta = data.get("chunk_meta", [])

        # 统计
        total_tokens = sum(len(tokens) for tokens in tokenized_corpus)
        all_tokens = [t for tokens in tokenized_corpus for t in tokens]
        token_freq = Counter(all_tokens)

        # 路径分布
        paths = [m.get("path", "") for m in chunk_meta]
        path_counts = Counter(paths)

        return {
            "total_docs": len(chunk_meta),
            "total_tokens": total_tokens,
            "unique_tokens": len(token_freq),
            "top_tokens": [{"token": t, "count": c} for t, c in token_freq.most_common(30)],
            "path_distribution": [{"path": p, "chunks": c} for p, c in path_counts.most_common(50)],
            "chunks": [
                {
                    "path": m.get("path", ""),
                    "title": m.get("title", ""),
                    "snippet": m.get("snippet", "")[:100],
                    "chunk_index": m.get("chunk_index", 0),
                }
                for m in chunk_meta[:100]
            ],
        }
    except FileNotFoundError:
        return {"total_docs": 0, "total_tokens": 0, "error": "BM25 index not found"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Helpers ─────────────────────────────────────────────────


def _safe_deserialize(serde, blob):
    """安全反序列化 BLOB，失败时返回大小信息"""
    if not blob:
        return None
    try:
        return serde.loads(blob)
    except Exception:
        return {"_deserialize_error": True, "blob_size": len(blob)}


def _safe_deserialize_typed(serde, type_str, value_blob):
    """反序列化 writes 表的 (type, value) 元组"""
    if not value_blob:
        return None
    try:
        return serde.loads_typed((type_str, value_blob))
    except Exception:
        try:
            return serde.loads(value_blob)
        except Exception:
            return {"_deserialize_error": True, "type": type_str, "blob_size": len(value_blob)}


def _summarize_checkpoint(data):
    """提取 checkpoint 的关键信息摘要"""
    if not data or not isinstance(data, dict):
        return None

    channel_values = data.get("channel_values", {})
    if not channel_values:
        return {"channels": list(data.keys())[:10]}

    summary = {}
    for key, val in channel_values.items():
        if isinstance(val, str):
            summary[key] = val[:200] + "..." if len(val) > 200 else val
        elif isinstance(val, list):
            summary[key] = f"[list: {len(val)} items]"
        elif isinstance(val, dict):
            summary[key] = f"{{dict: {len(val)} keys}}"
        elif val is None:
            summary[key] = None
        else:
            s = str(val)
            summary[key] = s[:200] + "..." if len(s) > 200 else s

    return summary


def _truncate_value(val, max_len=500):
    """截断过长的值用于显示"""
    if val is None:
        return None
    if isinstance(val, str):
        return val[:max_len] + "..." if len(val) > max_len else val
    if isinstance(val, (list, dict)):
        s = json.dumps(val, ensure_ascii=False, default=str)
        return s[:max_len] + "..." if len(s) > max_len else val
    return val
