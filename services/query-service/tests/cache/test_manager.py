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
