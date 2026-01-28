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
