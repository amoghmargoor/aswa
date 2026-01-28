from typing import Any
from uuid import UUID
import structlog

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range

from aswa_query.config import Settings
from .models import SearchResult, ContentType

logger = structlog.get_logger()


class VectorSearcher:
    """Search documents using vector similarity."""

    def __init__(
        self,
        settings: Settings,
        embedding_client: Any | None = None,
    ):
        self.settings = settings
        self.embedding_client = embedding_client
        self._qdrant_client: QdrantClient | None = None

    def _get_client(self) -> QdrantClient:
        if self._qdrant_client is None:
            self._qdrant_client = QdrantClient(url=self.settings.qdrant_url)
        return self._qdrant_client

    async def search(
        self,
        query: str,
        tenant_id: UUID,
        document_ids: list[UUID] | None = None,
        limit: int = 10,
        min_score: float = 0.5,
        offset: int = 0,
    ) -> list[SearchResult]:
        """Perform semantic search.

        Args:
            query: Search query text
            tenant_id: Tenant ID for isolation
            document_ids: Optional document scope
            limit: Maximum results
            min_score: Minimum similarity score
            offset: Result offset

        Returns:
            List of search results
        """
        # Generate query embedding
        query_embedding = await self._embed_query(query)

        # Build filter
        filter_conditions = [
            FieldCondition(
                key="tenant_id",
                match=MatchValue(value=str(tenant_id)),
            )
        ]

        if document_ids:
            filter_conditions.append(
                FieldCondition(
                    key="document_id",
                    match=MatchValue(value=[str(d) for d in document_ids]),
                )
            )

        # Execute search
        client = self._get_client()
        try:
            results = client.search(
                collection_name=self.settings.qdrant_collection,
                query_vector=query_embedding,
                query_filter=Filter(must=filter_conditions),
                limit=limit,
                offset=offset,
                score_threshold=min_score,
                with_payload=True,
            )

            search_results = []
            for result in results:
                payload = result.payload or {}
                search_results.append(SearchResult(
                    id=str(result.id),
                    content=payload.get("content", ""),
                    content_type=ContentType.DOCUMENT_CHUNK,
                    score=result.score,
                    document_id=UUID(payload["document_id"]) if payload.get("document_id") else None,
                    document_name=payload.get("document_name"),
                    chunk_index=payload.get("chunk_index"),
                    page_number=payload.get("page_number"),
                    metadata=payload.get("metadata", {}),
                ))

            logger.info(
                "Vector search completed",
                query_length=len(query),
                result_count=len(search_results),
            )

            return search_results

        except Exception as e:
            logger.error("Vector search failed", error=str(e))
            raise

    async def search_by_vector(
        self,
        vector: list[float],
        tenant_id: UUID,
        limit: int = 10,
        min_score: float = 0.5,
    ) -> list[SearchResult]:
        """Search using a pre-computed vector."""
        client = self._get_client()

        filter_conditions = [
            FieldCondition(
                key="tenant_id",
                match=MatchValue(value=str(tenant_id)),
            )
        ]

        results = client.search(
            collection_name=self.settings.qdrant_collection,
            query_vector=vector,
            query_filter=Filter(must=filter_conditions),
            limit=limit,
            score_threshold=min_score,
            with_payload=True,
        )

        return [
            SearchResult(
                id=str(r.id),
                content=r.payload.get("content", "") if r.payload else "",
                content_type=ContentType.DOCUMENT_CHUNK,
                score=r.score,
                document_id=UUID(r.payload["document_id"]) if r.payload and r.payload.get("document_id") else None,
                document_name=r.payload.get("document_name") if r.payload else None,
                metadata=r.payload.get("metadata", {}) if r.payload else {},
            )
            for r in results
        ]

    async def find_similar_chunks(
        self,
        chunk_id: str,
        tenant_id: UUID,
        limit: int = 5,
    ) -> list[SearchResult]:
        """Find chunks similar to a given chunk."""
        client = self._get_client()

        # Get the original chunk's vector
        points = client.retrieve(
            collection_name=self.settings.qdrant_collection,
            ids=[chunk_id],
            with_vectors=True,
        )

        if not points:
            return []

        vector = points[0].vector
        if isinstance(vector, dict):
            vector = list(vector.values())[0]

        return await self.search_by_vector(
            vector=vector,
            tenant_id=tenant_id,
            limit=limit + 1,  # Exclude self
        )[1:]  # Skip first (self)

    async def _embed_query(self, query: str) -> list[float]:
        """Generate embedding for query."""
        if self.embedding_client:
            return await self.embedding_client.embed(query)

        # Fallback: use a simple embedding service
        # In production, this should use the same embedding model as indexing
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.settings.qdrant_url.replace('6333', '8080')}/embed",
                json={"text": query},
                timeout=30.0,
            )
            if response.status_code == 200:
                return response.json()["embedding"]

        raise ValueError("No embedding client available")

    async def get_document_chunks(
        self,
        document_id: UUID,
        tenant_id: UUID,
    ) -> list[SearchResult]:
        """Get all chunks for a document."""
        client = self._get_client()

        results = client.scroll(
            collection_name=self.settings.qdrant_collection,
            scroll_filter=Filter(
                must=[
                    FieldCondition(key="tenant_id", match=MatchValue(value=str(tenant_id))),
                    FieldCondition(key="document_id", match=MatchValue(value=str(document_id))),
                ]
            ),
            with_payload=True,
            limit=1000,
        )

        chunks = []
        for point in results[0]:
            payload = point.payload or {}
            chunks.append(SearchResult(
                id=str(point.id),
                content=payload.get("content", ""),
                content_type=ContentType.DOCUMENT_CHUNK,
                score=1.0,
                document_id=document_id,
                document_name=payload.get("document_name"),
                chunk_index=payload.get("chunk_index"),
                page_number=payload.get("page_number"),
                metadata=payload.get("metadata", {}),
            ))

        # Sort by chunk index
        chunks.sort(key=lambda c: c.chunk_index or 0)
        return chunks
