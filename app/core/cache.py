"""
Redis cache layer — async, with graceful degradation.

All public functions silently return None / False when Redis is unavailable,
so the application keeps working without a running Redis instance.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_redis: Optional[aioredis.Redis] = None


async def init_redis() -> None:
    """Create the Redis connection pool.  Called once at startup."""
    global _redis
    try:
        _redis = aioredis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=settings.REDIS_TIMEOUT,
            socket_connect_timeout=settings.REDIS_TIMEOUT,
            retry_on_timeout=True,
        )
        # Quick connectivity check
        await _redis.ping()
        logger.info("Redis connected (%s)", settings.REDIS_URL)
    except Exception:
        logger.warning("Redis unavailable — caching disabled (non-fatal)")
        _redis = None


async def close_redis() -> None:
    """Close the connection pool.  Called once at shutdown."""
    global _redis
    if _redis is not None:
        try:
            await _redis.aclose()
        except Exception:
            pass
        _redis = None
        logger.info("Redis connection closed")


def _client() -> Optional[aioredis.Redis]:
    """Return the Redis client or None."""
    return _redis


def _key(key: str) -> str:
    """Prepend the configured key prefix."""
    return f"{settings.REDIS_KEY_PREFIX}{key}"


# ---------------------------------------------------------------------------
# String (JSON) operations
# ---------------------------------------------------------------------------


async def cache_get(key: str) -> Optional[Any]:
    """GET a JSON-serialized value.  Returns None on miss or error."""
    r = _client()
    if r is None:
        return None
    try:
        raw = await r.get(_key(key))
        if raw is None:
            return None
        return json.loads(raw)
    except Exception:
        logger.debug("cache_get(%s) failed", key, exc_info=True)
        return None


async def cache_set(key: str, value: Any, ttl: int = 300) -> bool:
    """SET a JSON-serialized value with TTL (seconds)."""
    r = _client()
    if r is None:
        return False
    try:
        await r.setex(_key(key), ttl, json.dumps(value, default=str))
        return True
    except Exception:
        logger.debug("cache_set(%s) failed", key, exc_info=True)
        return False


async def cache_delete(key: str) -> bool:
    """DEL a single key."""
    r = _client()
    if r is None:
        return False
    try:
        await r.delete(_key(key))
        return True
    except Exception:
        logger.debug("cache_delete(%s) failed", key, exc_info=True)
        return False


async def cache_delete_pattern(pattern: str) -> int:
    """Delete all keys matching *pattern* (uses SCAN to avoid blocking)."""
    r = _client()
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
        logger.debug("cache_delete_pattern(%s) failed", pattern, exc_info=True)
    return deleted


# ---------------------------------------------------------------------------
# Hash operations
# ---------------------------------------------------------------------------


async def cache_hgetall(key: str) -> Optional[Dict[str, str]]:
    """HGETALL — returns dict or None."""
    r = _client()
    if r is None:
        return None
    try:
        data = await r.hgetall(_key(key))
        return data if data else None
    except Exception:
        logger.debug("cache_hgetall(%s) failed", key, exc_info=True)
        return None


async def cache_hset(key: str, mapping: Dict[str, Any], ttl: int = 0) -> bool:
    """HSET multiple fields, optionally with TTL."""
    r = _client()
    if r is None:
        return False
    try:
        full_key = _key(key)
        args: List[str] = [full_key]
        for k, v in mapping.items():
            args.append(k)
            args.append(str(v))
        await r.execute_command("HSET", *args)
        if ttl > 0:
            await r.expire(full_key, ttl)
        return True
    except Exception:
        logger.debug("cache_hset(%s) failed", key, exc_info=True)
        return False


async def cache_hincrby(key: str, field: str, amount: int = 1) -> Optional[int]:
    """HINCRBY — atomically increment a hash field."""
    r = _client()
    if r is None:
        return None
    try:
        return await r.hincrby(_key(key), field, amount)
    except Exception:
        logger.debug("cache_hincrby(%s, %s) failed", key, field, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Counter operations
# ---------------------------------------------------------------------------


async def cache_incr(key: str, amount: int = 1) -> Optional[int]:
    """INCRBY — atomically increment a string value."""
    r = _client()
    if r is None:
        return None
    try:
        return await r.incrby(_key(key), amount)
    except Exception:
        logger.debug("cache_incr(%s) failed", key, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# List operations
# ---------------------------------------------------------------------------


async def cache_lpush(key: str, *values: Any) -> Optional[int]:
    """LPUSH — prepend values to a list."""
    r = _client()
    if r is None:
        return None
    try:
        serialized = [json.dumps(v, default=str) for v in values]
        return await r.lpush(_key(key), *serialized)
    except Exception:
        logger.debug("cache_lpush(%s) failed", key, exc_info=True)
        return None


async def cache_lrange(key: str, start: int = 0, end: int = -1) -> Optional[List[Any]]:
    """LRANGE — get elements from a list, JSON-deserialized."""
    r = _client()
    if r is None:
        return None
    try:
        raw = await r.lrange(_key(key), start, end)
        return [json.loads(item) for item in raw]
    except Exception:
        logger.debug("cache_lrange(%s) failed", key, exc_info=True)
        return None


async def cache_ltrim(key: str, start: int, end: int) -> bool:
    """LTRIM — trim a list to the specified range."""
    r = _client()
    if r is None:
        return False
    try:
        await r.ltrim(_key(key), start, end)
        return True
    except Exception:
        logger.debug("cache_ltrim(%s) failed", key, exc_info=True)
        return False


# ---------------------------------------------------------------------------
# Rate limiter (Sorted Set sliding window)
# ---------------------------------------------------------------------------


async def check_rate_limit(
    key: str,
    limit: int,
    window_seconds: int = 60,
) -> Tuple[bool, int]:
    """
    Sliding-window rate limiter using Sorted Set.

    Returns:
        (allowed, retry_after_seconds)
        - allowed=True:  request is within the limit
        - allowed=False: request exceeds the limit, retry_after > 0
    """
    r = _client()
    if r is None:
        # Redis down → allow everything
        return True, 0

    full_key = _key(f"ratelimit:{key}")
    now = time.time()
    window_start = now - window_seconds

    try:
        pipe = r.pipeline(transaction=True)
        # Remove entries outside the window
        pipe.zremrangebyscore(full_key, 0, window_start)
        # Add current request
        pipe.zadd(full_key, {f"{now}": now})
        # Count requests in window
        pipe.zcard(full_key)
        # Set expiry on the key itself (auto-cleanup)
        pipe.expire(full_key, window_seconds * 2)
        results = await pipe.execute()

        request_count = results[2]  # zcard result

        if request_count <= limit:
            return True, 0

        # Over limit — calculate retry-after from oldest entry in window
        oldest = await r.zrange(full_key, 0, 0, withscores=True)
        if oldest:
            retry_after = int(oldest[0][1] + window_seconds - now) + 1
        else:
            retry_after = window_seconds
        return False, max(retry_after, 1)

    except Exception:
        logger.debug("check_rate_limit(%s) failed — allowing", key, exc_info=True)
        return True, 0


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def hash_prompt(text: str) -> str:
    """SHA-256 hash for LLM cache keys."""
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
