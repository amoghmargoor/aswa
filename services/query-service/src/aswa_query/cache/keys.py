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
