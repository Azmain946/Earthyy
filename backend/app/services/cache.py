"""Small Redis-backed cache for catalogue searches and derived results."""
from __future__ import annotations

import logging

from redis import Redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_redis: Redis | None = None


def _client() -> Redis | None:
    global _redis
    if _redis is None:
        try:
            _redis = Redis.from_url(settings.redis_url, socket_connect_timeout=2)
            _redis.ping()
        except Exception:
            logger.warning("event=cache_unavailable")
            _redis = None
    return _redis


def cache_get(key: str) -> str | None:
    c = _client()
    if c is None:
        return None
    try:
        val = c.get(f"earthyy:{key}")
        return val.decode() if val else None
    except Exception:
        return None


def cache_set(key: str, value: str, ttl: int | None = None) -> None:
    c = _client()
    if c is None:
        return
    try:
        c.setex(f"earthyy:{key}", ttl or settings.stac_search_cache_ttl, value)
    except Exception:
        pass
