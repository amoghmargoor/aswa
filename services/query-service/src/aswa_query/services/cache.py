from typing import Any
from uuid import UUID
import json

import redis.asyncio as redis
import structlog

logger = structlog.get_logger()


class CacheService:
    """Redis-based caching service."""

    def __init__(self, redis_url: str, default_ttl: int = 3600):
        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self._client: redis.Redis | None = None

    async def _get_client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.from_url(self.redis_url)
        return self._client

    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        try:
            client = await self._get_client()
            value = await client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.warning("Cache get failed", key=key, error=str(e))
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Set value in cache."""
        try:
            client = await self._get_client()
            await client.setex(
                key,
                ttl or self.default_ttl,
                json.dumps(value, default=str),
            )
            return True
        except Exception as e:
            logger.warning("Cache set failed", key=key, error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        try:
            client = await self._get_client()
            await client.delete(key)
            return True
        except Exception as e:
            logger.warning("Cache delete failed", key=key, error=str(e))
            return False

    async def get_query_result(self, query_id: UUID) -> dict | None:
        """Get cached query result."""
        return await self.get(f"query:{query_id}")

    async def set_query_result(self, query_id: UUID, result: dict, ttl: int | None = None) -> bool:
        """Cache query result."""
        return await self.set(f"query:{query_id}", result, ttl)

    async def get_query_cache(self, tenant_id: UUID, query_hash: str) -> dict | None:
        """Get cached response for a query."""
        return await self.get(f"cache:{tenant_id}:{query_hash}")

    async def set_query_cache(self, tenant_id: UUID, query_hash: str, result: dict, ttl: int | None = None) -> bool:
        """Cache query response."""
        return await self.set(f"cache:{tenant_id}:{query_hash}", result, ttl)

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None
