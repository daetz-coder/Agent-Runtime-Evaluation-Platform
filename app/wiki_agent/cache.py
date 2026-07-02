"""Wiki Agent 本地缓存层 — Redis 可选，优雅降级。

提供与 app.core.cache 相同的接口，使 wiki_agent 可以脱离评估平台独立运行。
Redis 不可用时所有函数静默返回 None / False。
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

_redis = None
_redis_initialized = False


async def _get_redis():
    """懒加载 Redis 连接（仅在环境变量 REDIS_URL 存在时尝试连接）。"""
    global _redis, _redis_initialized
    if _redis_initialized:
        return _redis
    _redis_initialized = True

    redis_url = os.environ.get("REDIS_URL", "")
    if not redis_url:
        return None
    try:
        import redis.asyncio as aioredis

        _redis = aioredis.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_timeout=2,
            socket_connect_timeout=2,
        )
        await _redis.ping()
        logger.info("[Wiki Agent Cache] Redis connected (%s)", redis_url)
    except Exception:
        logger.info("[Wiki Agent Cache] Redis unavailable — caching disabled")
        _redis = None
    return _redis


def _key(key: str) -> str:
    return f"wiki:{key}"


async def cache_get(key: str) -> Optional[Any]:
    r = await _get_redis()
    if r is None:
        return None
    try:
        raw = await r.get(_key(key))
        if raw is None:
            return None
        return json.loads(raw)
    except Exception:
        return None


async def cache_set(key: str, value: Any, ttl: int = 300) -> bool:
    r = await _get_redis()
    if r is None:
        return False
    try:
        await r.setex(_key(key), ttl, json.dumps(value, default=str))
        return True
    except Exception:
        return False


async def cache_set_nx(key: str, value: Any, ttl: int = 300) -> bool:
    r = await _get_redis()
    if r is None:
        return False
    try:
        created = await r.set(_key(key), json.dumps(value, default=str), nx=True, ex=ttl)
        return bool(created)
    except Exception:
        return False


async def cache_delete(key: str) -> bool:
    r = await _get_redis()
    if r is None:
        return False
    try:
        await r.delete(_key(key))
        return True
    except Exception:
        return False


async def cache_delete_pattern(pattern: str) -> int:
    r = await _get_redis()
    if r is None:
        return 0
    full_pattern = _key(pattern)
    deleted = 0
    try:
        cursor = 0
        while True:
            cursor, keys = await r.scan(cursor=cursor, match=full_pattern, count=100)
            if keys:
                deleted += await r.delete(*keys)
            if cursor == 0:
                break
    except Exception:
        pass
    return deleted


def hash_prompt(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
