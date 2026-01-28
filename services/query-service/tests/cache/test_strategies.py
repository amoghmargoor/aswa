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
