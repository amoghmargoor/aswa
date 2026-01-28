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
