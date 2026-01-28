import json
from typing import Any, TypeVar, Generic
from uuid import UUID
import redis.asyncio as redis
import structlog

from .keys import CacheKeyBuilder
from .strategies import CacheStrategy, TTLStrategy

logger = structlog.get_logger()

T = TypeVar("T")


class CacheManager:
    """Main cache manager for query service."""

    def __init__(
        self,
        redis_url: str,
        key_builder: CacheKeyBuilder | None = None,
        strategy: CacheStrategy | None = None,
        default_ttl: int = 3600,
    ):
        self.redis_url = redis_url
        self.key_builder = key_builder or CacheKeyBuilder()
        self.strategy = strategy or TTLStrategy(default_ttl=default_ttl)
        self.default_ttl = default_ttl
        self._client: redis.Redis | None = None
        self._stats = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0}

    async def _get_client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.from_url(self.redis_url)
        return self._client

    async def get(self, key: str) -> Any | None:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        try:
            client = await self._get_client()
            value = await client.get(key)

            if value:
                self._stats["hits"] += 1
                logger.debug("Cache hit", key=key)
                return json.loads(value)

            self._stats["misses"] += 1
            return None

        except Exception as e:
            logger.warning("Cache get failed", key=key, error=str(e))
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> bool:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Optional TTL override

        Returns:
            True if successful
        """
        if not self.strategy.should_cache(key, value):
            return False

        try:
            client = await self._get_client()
            ttl = ttl or self.strategy.get_ttl(key, value)

            await client.setex(
                key,
                ttl,
                json.dumps(value, default=str),
            )

            self._stats["sets"] += 1
            logger.debug("Cache set", key=key, ttl=ttl)
            return True

        except Exception as e:
            logger.warning("Cache set failed", key=key, error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        """Delete from cache.

        Args:
            key: Cache key

        Returns:
            True if deleted
        """
        try:
            client = await self._get_client()
            await client.delete(key)
            self._stats["deletes"] += 1
            return True
        except Exception as e:
            logger.warning("Cache delete failed", key=key, error=str(e))
            return False

    async def get_query_result(
        self,
        tenant_id: UUID,
        query_hash: str,
    ) -> dict | None:
        """Get cached query result."""
        key = self.key_builder.query_result_key(tenant_id, query_hash)
        return await self.get(key)

    async def set_query_result(
        self,
        tenant_id: UUID,
        query_hash: str,
        result: dict,
        ttl: int | None = None,
    ) -> bool:
        """Cache query result."""
        key = self.key_builder.query_result_key(tenant_id, query_hash)
        return await self.set(key, result, ttl)

    async def get_retrieval(
        self,
        tenant_id: UUID,
        query_hash: str,
    ) -> dict | None:
        """Get cached retrieval result."""
        key = self.key_builder.retrieval_key(tenant_id, query_hash)
        return await self.get(key)

    async def set_retrieval(
        self,
        tenant_id: UUID,
        query_hash: str,
        result: dict,
        ttl: int | None = None,
    ) -> bool:
        """Cache retrieval result."""
        key = self.key_builder.retrieval_key(tenant_id, query_hash)
        return await self.set(key, result, ttl)

    async def get_generation(
        self,
        tenant_id: UUID,
        query_hash: str,
        context_hash: str,
    ) -> dict | None:
        """Get cached generation result."""
        key = self.key_builder.generation_key(tenant_id, query_hash, context_hash)
        return await self.get(key)

    async def set_generation(
        self,
        tenant_id: UUID,
        query_hash: str,
        context_hash: str,
        result: dict,
        ttl: int | None = None,
    ) -> bool:
        """Cache generation result."""
        key = self.key_builder.generation_key(tenant_id, query_hash, context_hash)
        return await self.set(key, result, ttl)

    async def get_embedding(self, text_hash: str) -> list[float] | None:
        """Get cached embedding."""
        key = self.key_builder.embedding_key(text_hash)
        return await self.get(key)

    async def set_embedding(
        self,
        text_hash: str,
        embedding: list[float],
    ) -> bool:
        """Cache embedding."""
        key = self.key_builder.embedding_key(text_hash)
        return await self.set(key, embedding, ttl=86400)  # 24 hours

    async def invalidate_tenant(self, tenant_id: UUID) -> int:
        """Invalidate all cache entries for a tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            Number of keys deleted
        """
        try:
            client = await self._get_client()
            pattern = self.key_builder.tenant_pattern(tenant_id)

            deleted = 0
            cursor = 0

            while True:
                cursor, keys = await client.scan(cursor, match=pattern, count=100)
                if keys:
                    await client.delete(*keys)
                    deleted += len(keys)
                if cursor == 0:
                    break

            logger.info("Tenant cache invalidated", tenant_id=str(tenant_id), deleted=deleted)
            return deleted

        except Exception as e:
            logger.error("Tenant invalidation failed", error=str(e))
            return 0

    async def invalidate_document(
        self,
        tenant_id: UUID,
        document_id: UUID,
    ) -> int:
        """Invalidate cache entries related to a document."""
        # This requires more sophisticated tracking
        # For now, invalidate all tenant cache
        return await self.invalidate_tenant(tenant_id)

    def get_stats(self) -> dict:
        """Get cache statistics."""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total if total > 0 else 0

        return {
            **self._stats,
            "hit_rate": round(hit_rate, 3),
            "total_requests": total,
        }

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None
