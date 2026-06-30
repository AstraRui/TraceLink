"""Redis-backed L1 cache for hot short links.

Only the mapping ``short_code -> original_url`` is cached. Entries are stored
with a TTL never longer than the link's own expiry (computed by the caller), so
a cache hit always means the link is still valid — no second expiry check needed.
"""

from __future__ import annotations

import redis.asyncio as redis

from app.core.config import settings

_KEY_PREFIX = "link:"

_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """Lazily build a shared async Redis client (one per process)."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


class LinkCache:
    def __init__(self, client: redis.Redis, default_ttl: int) -> None:
        self._client = client
        self._default_ttl = default_ttl

    @staticmethod
    def _key(code: str) -> str:
        return f"{_KEY_PREFIX}{code}"

    async def get_url(self, code: str) -> str | None:
        # decode_responses=True yields str, but the type is bytes | str | None;
        # normalize defensively.
        value = await self._client.get(self._key(code))
        if value is None:
            return None
        return value if isinstance(value, str) else value.decode()

    async def set_url(self, code: str, url: str, ttl: int | None = None) -> None:
        await self._client.set(self._key(code), url, ex=ttl or self._default_ttl)

    async def invalidate(self, code: str) -> None:
        await self._client.delete(self._key(code))


def get_cache() -> LinkCache:
    """FastAPI dependency: a cache bound to the shared Redis client."""
    return LinkCache(get_redis(), settings.cache_ttl_seconds)
