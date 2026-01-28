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
