# Task 4.2.3: Query Caching (Redis)

## Context

You are working on the ASWA query-service at `/services/query-service/`. The query processing and answer generation are implemented. Now we need to add caching to improve performance and reduce LLM costs.

## Objective

Create a comprehensive caching layer that:
1. Caches query results with configurable TTL
2. Supports cache invalidation strategies
3. Provides cache analytics and hit rates
4. Handles tenant isolation
5. Supports partial cache (retrieval vs. generation)

## Requirements

### 1. Create `/services/query-service/src/aswa_query/cache/__init__.py`
```python
from .manager import CacheManager
from .keys import CacheKeyBuilder
from .strategies import CacheStrategy, TTLStrategy, LRUStrategy
from .invalidation import CacheInvalidator
from .analytics import CacheAnalytics

__all__ = [
    "CacheManager",
    "CacheKeyBuilder",
    "CacheStrategy",
    "TTLStrategy",
    "LRUStrategy",
    "CacheInvalidator",
    "CacheAnalytics",
]
```

### 2. Create `/services/query-service/src/aswa_query/cache/keys.py`
```python
import hashlib
from typing import Any
from uuid import UUID


class CacheKeyBuilder:
    """Build cache keys for different cache types."""

    def __init__(self, prefix: str = "aswa"):
        self.prefix = prefix

    def query_result_key(
        self,
        tenant_id: UUID,
        query_hash: str,
    ) -> str:
        """Build key for query result cache."""
        return f"{self.prefix}:query:{tenant_id}:{query_hash}"

    def retrieval_key(
        self,
        tenant_id: UUID,
        query_hash: str,
    ) -> str:
        """Build key for retrieval cache."""
        return f"{self.prefix}:retrieval:{tenant_id}:{query_hash}"

    def generation_key(
        self,
        tenant_id: UUID,
        query_hash: str,
        context_hash: str,
    ) -> str:
        """Build key for generation cache."""
        return f"{self.prefix}:gen:{tenant_id}:{query_hash}:{context_hash}"

    def embedding_key(
        self,
        text_hash: str,
    ) -> str:
        """Build key for embedding cache."""
        return f"{self.prefix}:embed:{text_hash}"

    def insight_key(
        self,
        tenant_id: UUID,
        insight_id: UUID,
    ) -> str:
        """Build key for insight cache."""
        return f"{self.prefix}:insight:{tenant_id}:{insight_id}"

    def tenant_pattern(self, tenant_id: UUID) -> str:
        """Pattern to match all keys for a tenant."""
        return f"{self.prefix}:*:{tenant_id}:*"

    @staticmethod
    def hash_query(
        query: str,
        document_ids: list[UUID] | None = None,
        filters: dict | None = None,
    ) -> str:
        """Generate hash for query caching."""
        components = [query.lower().strip()]

        if document_ids:
            components.append(":".join(sorted(str(d) for d in document_ids)))

        if filters:
            components.append(str(sorted(filters.items())))

        content = "|".join(components)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    @staticmethod
    def hash_context(context: str) -> str:
        """Generate hash for context."""
        return hashlib.sha256(context.encode()).hexdigest()[:16]
```

### 3. Create `/services/query-service/src/aswa_query/cache/strategies.py`
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


@dataclass
class CacheEntry:
    """A cached entry with metadata."""
    value: Any
    created_at: datetime
    expires_at: datetime | None
    access_count: int = 0
    last_accessed: datetime | None = None
    size_bytes: int = 0


class CacheStrategy(ABC):
    """Abstract cache strategy."""

    @abstractmethod
    def should_cache(self, key: str, value: Any) -> bool:
        """Determine if value should be cached."""
        ...

    @abstractmethod
    def get_ttl(self, key: str, value: Any) -> int:
        """Get TTL for cache entry."""
        ...

    @abstractmethod
    def should_evict(self, entry: CacheEntry) -> bool:
        """Determine if entry should be evicted."""
        ...


class TTLStrategy(CacheStrategy):
    """Time-to-live based cache strategy."""

    def __init__(
        self,
        default_ttl: int = 3600,
        max_ttl: int = 86400,
        min_ttl: int = 60,
    ):
        self.default_ttl = default_ttl
        self.max_ttl = max_ttl
        self.min_ttl = min_ttl

        # TTL by key type
        self.ttl_map = {
            "query": 3600,      # 1 hour
            "retrieval": 1800,  # 30 minutes
            "gen": 7200,        # 2 hours
            "embed": 86400,     # 24 hours
            "insight": 600,     # 10 minutes
        }

    def should_cache(self, key: str, value: Any) -> bool:
        """Always cache if value exists."""
        return value is not None

    def get_ttl(self, key: str, value: Any) -> int:
        """Get TTL based on key type."""
        for key_type, ttl in self.ttl_map.items():
            if f":{key_type}:" in key:
                return ttl
        return self.default_ttl

    def should_evict(self, entry: CacheEntry) -> bool:
        """Evict if expired."""
        if entry.expires_at:
            return datetime.utcnow() > entry.expires_at
        return False


class LRUStrategy(CacheStrategy):
    """Least Recently Used cache strategy."""

    def __init__(
        self,
        max_entries: int = 10000,
        max_memory_mb: int = 100,
        min_access_interval: int = 60,
    ):
        self.max_entries = max_entries
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.min_access_interval = min_access_interval

    def should_cache(self, key: str, value: Any) -> bool:
        """Cache if value exists and isn't too large."""
        if value is None:
            return False
        # Rough size check
        import sys
        size = sys.getsizeof(str(value))
        return size < self.max_memory_bytes * 0.1  # Max 10% of total

    def get_ttl(self, key: str, value: Any) -> int:
        """LRU doesn't use TTL directly."""
        return 86400  # 24 hours max

    def should_evict(self, entry: CacheEntry) -> bool:
        """Evict based on access patterns."""
        now = datetime.utcnow()

        # Never accessed after creation
        if not entry.last_accessed:
            return (now - entry.created_at).seconds > 300

        # Not accessed recently
        time_since_access = (now - entry.last_accessed).seconds
        return time_since_access > 3600 and entry.access_count < 5


class AdaptiveStrategy(CacheStrategy):
    """Adaptive strategy based on query patterns."""

    def __init__(self):
        self.ttl_strategy = TTLStrategy()
        self.query_stats: dict[str, dict] = {}

    def should_cache(self, key: str, value: Any) -> bool:
        """Cache based on value and historical patterns."""
        if value is None:
            return False

        # Check if similar queries are frequently accessed
        key_prefix = ":".join(key.split(":")[:3])
        stats = self.query_stats.get(key_prefix, {})

        if stats.get("hit_rate", 0) < 0.1:
            # Low hit rate, maybe don't cache
            return stats.get("query_count", 0) > 10

        return True

    def get_ttl(self, key: str, value: Any) -> int:
        """Adaptive TTL based on access patterns."""
        key_prefix = ":".join(key.split(":")[:3])
        stats = self.query_stats.get(key_prefix, {})

        base_ttl = self.ttl_strategy.get_ttl(key, value)

        # Increase TTL for frequently accessed
        if stats.get("hit_rate", 0) > 0.5:
            return min(base_ttl * 2, 86400)

        # Decrease TTL for rarely accessed
        if stats.get("hit_rate", 0) < 0.1:
            return max(base_ttl // 2, 300)

        return base_ttl

    def should_evict(self, entry: CacheEntry) -> bool:
        """Evict based on access patterns and TTL."""
        return self.ttl_strategy.should_evict(entry)

    def record_access(self, key: str, is_hit: bool) -> None:
        """Record cache access for adaptive behavior."""
        key_prefix = ":".join(key.split(":")[:3])

        if key_prefix not in self.query_stats:
            self.query_stats[key_prefix] = {"hits": 0, "misses": 0, "query_count": 0}

        stats = self.query_stats[key_prefix]
        stats["query_count"] += 1

        if is_hit:
            stats["hits"] += 1
        else:
            stats["misses"] += 1

        total = stats["hits"] + stats["misses"]
        stats["hit_rate"] = stats["hits"] / total if total > 0 else 0
```

### 4. Create `/services/query-service/src/aswa_query/cache/manager.py`
```python
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
```

### 5. Create `/services/query-service/src/aswa_query/cache/invalidation.py`
```python
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID
import structlog

from .manager import CacheManager
from .keys import CacheKeyBuilder

logger = structlog.get_logger()


class InvalidationEvent:
    """An event that triggers cache invalidation."""

    def __init__(
        self,
        event_type: str,
        tenant_id: UUID,
        resource_id: UUID | None = None,
        metadata: dict | None = None,
    ):
        self.event_type = event_type
        self.tenant_id = tenant_id
        self.resource_id = resource_id
        self.metadata = metadata or {}
        self.timestamp = datetime.utcnow()


class CacheInvalidator:
    """Handle cache invalidation based on events."""

    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager
        self.key_builder = CacheKeyBuilder()

        # Event handlers
        self._handlers = {
            "document_updated": self._handle_document_update,
            "document_deleted": self._handle_document_delete,
            "insight_updated": self._handle_insight_update,
            "insight_deleted": self._handle_insight_delete,
            "tenant_config_changed": self._handle_tenant_config_change,
        }

    async def handle_event(self, event: InvalidationEvent) -> int:
        """Process an invalidation event.

        Args:
            event: Invalidation event

        Returns:
            Number of keys invalidated
        """
        handler = self._handlers.get(event.event_type)
        if handler:
            return await handler(event)

        logger.warning("Unknown invalidation event", event_type=event.event_type)
        return 0

    async def _handle_document_update(self, event: InvalidationEvent) -> int:
        """Handle document update - invalidate related caches."""
        return await self.cache.invalidate_document(
            event.tenant_id,
            event.resource_id,
        )

    async def _handle_document_delete(self, event: InvalidationEvent) -> int:
        """Handle document deletion."""
        return await self.cache.invalidate_document(
            event.tenant_id,
            event.resource_id,
        )

    async def _handle_insight_update(self, event: InvalidationEvent) -> int:
        """Handle insight update."""
        if event.resource_id:
            key = self.key_builder.insight_key(event.tenant_id, event.resource_id)
            await self.cache.delete(key)
            return 1
        return 0

    async def _handle_insight_delete(self, event: InvalidationEvent) -> int:
        """Handle insight deletion."""
        return await self._handle_insight_update(event)

    async def _handle_tenant_config_change(self, event: InvalidationEvent) -> int:
        """Handle tenant configuration change - full invalidation."""
        return await self.cache.invalidate_tenant(event.tenant_id)

    async def schedule_cleanup(
        self,
        tenant_id: UUID,
        delay_seconds: int = 300,
    ) -> None:
        """Schedule a cache cleanup for later.

        Args:
            tenant_id: Tenant ID
            delay_seconds: Delay before cleanup
        """
        # In production, this would use a task queue
        logger.info(
            "Cache cleanup scheduled",
            tenant_id=str(tenant_id),
            delay=delay_seconds,
        )


class CacheWarmer:
    """Pre-warm cache with common queries."""

    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager

    async def warm_common_queries(
        self,
        tenant_id: UUID,
        queries: list[str],
        query_processor: Any,
    ) -> int:
        """Warm cache with common queries.

        Args:
            tenant_id: Tenant ID
            queries: List of common queries
            query_processor: Query processor to execute queries

        Returns:
            Number of queries warmed
        """
        warmed = 0

        for query in queries:
            try:
                # Execute query to populate cache
                await query_processor.process(tenant_id, query)
                warmed += 1
            except Exception as e:
                logger.warning("Failed to warm query", query=query, error=str(e))

        logger.info("Cache warming complete", warmed=warmed, total=len(queries))
        return warmed

    async def warm_from_history(
        self,
        tenant_id: UUID,
        query_processor: Any,
        limit: int = 100,
    ) -> int:
        """Warm cache from query history.

        Args:
            tenant_id: Tenant ID
            query_processor: Query processor
            limit: Max queries to warm

        Returns:
            Number of queries warmed
        """
        # Would fetch from query history service
        # For now, return 0
        return 0
```

### 6. Create `/services/query-service/src/aswa_query/cache/analytics.py`
```python
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID
import redis.asyncio as redis
import structlog

logger = structlog.get_logger()


@dataclass
class CacheMetrics:
    """Cache metrics for a time period."""
    period_start: datetime
    period_end: datetime
    total_requests: int = 0
    hits: int = 0
    misses: int = 0
    hit_rate: float = 0.0
    avg_latency_ms: float = 0.0
    memory_usage_mb: float = 0.0
    key_count: int = 0
    evictions: int = 0

    @property
    def miss_rate(self) -> float:
        return 1.0 - self.hit_rate


@dataclass
class TenantCacheMetrics:
    """Cache metrics per tenant."""
    tenant_id: UUID
    key_count: int = 0
    memory_bytes: int = 0
    hit_rate: float = 0.0
    most_accessed_keys: list[str] = field(default_factory=list)


class CacheAnalytics:
    """Analytics for cache performance."""

    def __init__(self, redis_url: str, metrics_prefix: str = "aswa:metrics"):
        self.redis_url = redis_url
        self.metrics_prefix = metrics_prefix
        self._client: redis.Redis | None = None

    async def _get_client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.from_url(self.redis_url)
        return self._client

    async def record_access(
        self,
        key: str,
        is_hit: bool,
        latency_ms: float,
        tenant_id: UUID | None = None,
    ) -> None:
        """Record a cache access for analytics.

        Args:
            key: Cache key accessed
            is_hit: Whether it was a hit
            latency_ms: Access latency
            tenant_id: Optional tenant ID
        """
        try:
            client = await self._get_client()
            now = datetime.utcnow()
            hour_bucket = now.strftime("%Y%m%d%H")

            # Increment counters
            pipe = client.pipeline()

            # Global metrics
            if is_hit:
                pipe.hincrby(f"{self.metrics_prefix}:{hour_bucket}", "hits", 1)
            else:
                pipe.hincrby(f"{self.metrics_prefix}:{hour_bucket}", "misses", 1)

            pipe.hincrbyfloat(f"{self.metrics_prefix}:{hour_bucket}", "total_latency", latency_ms)
            pipe.hincrby(f"{self.metrics_prefix}:{hour_bucket}", "requests", 1)

            # Tenant metrics
            if tenant_id:
                tenant_key = f"{self.metrics_prefix}:tenant:{tenant_id}:{hour_bucket}"
                if is_hit:
                    pipe.hincrby(tenant_key, "hits", 1)
                else:
                    pipe.hincrby(tenant_key, "misses", 1)

            # Set expiry (keep 7 days of metrics)
            pipe.expire(f"{self.metrics_prefix}:{hour_bucket}", 604800)

            await pipe.execute()

        except Exception as e:
            logger.warning("Failed to record cache metrics", error=str(e))

    async def get_metrics(
        self,
        hours: int = 24,
    ) -> CacheMetrics:
        """Get cache metrics for a time period.

        Args:
            hours: Number of hours to analyze

        Returns:
            CacheMetrics
        """
        client = await self._get_client()

        now = datetime.utcnow()
        start = now - timedelta(hours=hours)

        total_hits = 0
        total_misses = 0
        total_latency = 0.0
        total_requests = 0

        for hour_offset in range(hours):
            bucket_time = start + timedelta(hours=hour_offset)
            bucket_key = f"{self.metrics_prefix}:{bucket_time.strftime('%Y%m%d%H')}"

            data = await client.hgetall(bucket_key)
            if data:
                total_hits += int(data.get(b"hits", 0))
                total_misses += int(data.get(b"misses", 0))
                total_latency += float(data.get(b"total_latency", 0))
                total_requests += int(data.get(b"requests", 0))

        hit_rate = total_hits / (total_hits + total_misses) if (total_hits + total_misses) > 0 else 0
        avg_latency = total_latency / total_requests if total_requests > 0 else 0

        # Get memory info
        info = await client.info("memory")
        memory_mb = info.get("used_memory", 0) / (1024 * 1024)

        # Get key count
        key_count = await client.dbsize()

        return CacheMetrics(
            period_start=start,
            period_end=now,
            total_requests=total_requests,
            hits=total_hits,
            misses=total_misses,
            hit_rate=round(hit_rate, 3),
            avg_latency_ms=round(avg_latency, 2),
            memory_usage_mb=round(memory_mb, 2),
            key_count=key_count,
        )

    async def get_tenant_metrics(
        self,
        tenant_id: UUID,
        hours: int = 24,
    ) -> TenantCacheMetrics:
        """Get cache metrics for a specific tenant.

        Args:
            tenant_id: Tenant ID
            hours: Number of hours to analyze

        Returns:
            TenantCacheMetrics
        """
        client = await self._get_client()

        now = datetime.utcnow()
        start = now - timedelta(hours=hours)

        total_hits = 0
        total_misses = 0

        for hour_offset in range(hours):
            bucket_time = start + timedelta(hours=hour_offset)
            bucket_key = f"{self.metrics_prefix}:tenant:{tenant_id}:{bucket_time.strftime('%Y%m%d%H')}"

            data = await client.hgetall(bucket_key)
            if data:
                total_hits += int(data.get(b"hits", 0))
                total_misses += int(data.get(b"misses", 0))

        hit_rate = total_hits / (total_hits + total_misses) if (total_hits + total_misses) > 0 else 0

        # Count tenant keys
        pattern = f"aswa:*:{tenant_id}:*"
        key_count = 0
        cursor = 0
        while True:
            cursor, keys = await client.scan(cursor, match=pattern, count=100)
            key_count += len(keys)
            if cursor == 0:
                break

        return TenantCacheMetrics(
            tenant_id=tenant_id,
            key_count=key_count,
            hit_rate=round(hit_rate, 3),
        )

    async def get_hot_keys(
        self,
        limit: int = 10,
    ) -> list[dict]:
        """Get most frequently accessed keys.

        Args:
            limit: Number of keys to return

        Returns:
            List of hot key info
        """
        # This would require additional tracking
        # For now, return empty list
        return []

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None
```

## Test Requirements

### Create `/services/query-service/tests/cache/__init__.py`

### Create `/services/query-service/tests/cache/test_keys.py`
```python
import pytest
from uuid import uuid4

from aswa_query.cache.keys import CacheKeyBuilder


class TestCacheKeyBuilder:
    @pytest.fixture
    def builder(self):
        return CacheKeyBuilder()

    def test_query_result_key(self, builder):
        """Test query result key generation."""
        tenant_id = uuid4()
        query_hash = "abc123"

        key = builder.query_result_key(tenant_id, query_hash)

        assert "query" in key
        assert str(tenant_id) in key
        assert query_hash in key

    def test_hash_query_consistency(self, builder):
        """Test query hash is consistent."""
        hash1 = builder.hash_query("What are the risks?")
        hash2 = builder.hash_query("What are the risks?")
        hash3 = builder.hash_query("What are the opportunities?")

        assert hash1 == hash2
        assert hash1 != hash3

    def test_hash_query_case_insensitive(self, builder):
        """Test query hash is case insensitive."""
        hash1 = builder.hash_query("What Are The Risks?")
        hash2 = builder.hash_query("what are the risks?")

        assert hash1 == hash2

    def test_tenant_pattern(self, builder):
        """Test tenant pattern generation."""
        tenant_id = uuid4()

        pattern = builder.tenant_pattern(tenant_id)

        assert "*" in pattern
        assert str(tenant_id) in pattern
```

### Create `/services/query-service/tests/cache/test_manager.py`
```python
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from aswa_query.cache.manager import CacheManager


class TestCacheManager:
    @pytest.fixture
    def cache_manager(self):
        return CacheManager("redis://localhost:6379")

    @pytest.mark.asyncio
    async def test_get_miss(self, cache_manager):
        """Test cache miss."""
        with patch.object(cache_manager, '_get_client') as mock_client:
            mock_redis = AsyncMock()
            mock_redis.get.return_value = None
            mock_client.return_value = mock_redis

            result = await cache_manager.get("nonexistent_key")

            assert result is None
            assert cache_manager._stats["misses"] == 1

    @pytest.mark.asyncio
    async def test_get_hit(self, cache_manager):
        """Test cache hit."""
        with patch.object(cache_manager, '_get_client') as mock_client:
            mock_redis = AsyncMock()
            mock_redis.get.return_value = b'{"key": "value"}'
            mock_client.return_value = mock_redis

            result = await cache_manager.get("existing_key")

            assert result == {"key": "value"}
            assert cache_manager._stats["hits"] == 1

    @pytest.mark.asyncio
    async def test_set(self, cache_manager):
        """Test cache set."""
        with patch.object(cache_manager, '_get_client') as mock_client:
            mock_redis = AsyncMock()
            mock_client.return_value = mock_redis

            result = await cache_manager.set("key", {"data": "value"})

            assert result is True
            mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_query_result(self, cache_manager):
        """Test getting query result."""
        tenant_id = uuid4()
        query_hash = "abc123"

        with patch.object(cache_manager, 'get') as mock_get:
            mock_get.return_value = {"answer": "test"}

            result = await cache_manager.get_query_result(tenant_id, query_hash)

            assert result == {"answer": "test"}

    def test_get_stats(self, cache_manager):
        """Test statistics retrieval."""
        cache_manager._stats = {"hits": 80, "misses": 20, "sets": 50, "deletes": 5}

        stats = cache_manager.get_stats()

        assert stats["hit_rate"] == 0.8
        assert stats["total_requests"] == 100
```

### Create `/services/query-service/tests/cache/test_strategies.py`
```python
import pytest
from datetime import datetime, timedelta

from aswa_query.cache.strategies import TTLStrategy, LRUStrategy, CacheEntry


class TestTTLStrategy:
    @pytest.fixture
    def strategy(self):
        return TTLStrategy()

    def test_should_cache(self, strategy):
        """Test caching decision."""
        assert strategy.should_cache("key", "value") is True
        assert strategy.should_cache("key", None) is False

    def test_get_ttl_by_key_type(self, strategy):
        """Test TTL varies by key type."""
        query_ttl = strategy.get_ttl("aswa:query:tenant:hash", {})
        embed_ttl = strategy.get_ttl("aswa:embed:hash", {})

        assert query_ttl < embed_ttl  # Queries expire faster

    def test_should_evict_expired(self, strategy):
        """Test eviction of expired entries."""
        expired_entry = CacheEntry(
            value="test",
            created_at=datetime.utcnow() - timedelta(hours=2),
            expires_at=datetime.utcnow() - timedelta(hours=1),
        )

        assert strategy.should_evict(expired_entry) is True

    def test_should_not_evict_valid(self, strategy):
        """Test non-eviction of valid entries."""
        valid_entry = CacheEntry(
            value="test",
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )

        assert strategy.should_evict(valid_entry) is False


class TestLRUStrategy:
    @pytest.fixture
    def strategy(self):
        return LRUStrategy()

    def test_should_evict_never_accessed(self, strategy):
        """Test eviction of never-accessed entries."""
        entry = CacheEntry(
            value="test",
            created_at=datetime.utcnow() - timedelta(minutes=10),
            expires_at=None,
            last_accessed=None,
        )

        assert strategy.should_evict(entry) is True

    def test_should_not_evict_recently_accessed(self, strategy):
        """Test non-eviction of recently accessed entries."""
        entry = CacheEntry(
            value="test",
            created_at=datetime.utcnow() - timedelta(hours=1),
            expires_at=None,
            last_accessed=datetime.utcnow() - timedelta(minutes=5),
            access_count=10,
        )

        assert strategy.should_evict(entry) is False
```

## Verification

1. Run tests: `cd /services/query-service && python -m pytest tests/cache/ -v`
2. Verify imports: `python -c "from aswa_query.cache import CacheManager"`
3. Test with Redis: Start Redis and run integration tests
