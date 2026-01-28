"""Tests for Qdrant vector store implementation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from aswa_ingestion.vectorstore.base import (
    VectorRecord,
    SearchFilter,
    FilterOperator,
)
from aswa_ingestion.vectorstore.qdrant import QdrantVectorStore
from aswa_ingestion.vectorstore.hybrid import HybridSearcher, ReRanker, normalize_scores, HybridResult


class TestQdrantVectorStore:
    """Tests for QdrantVectorStore."""

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        """Create mock Qdrant client."""
        client = AsyncMock()
        client.get_collections = AsyncMock(return_value=MagicMock(collections=[]))
        client.get_collection = AsyncMock()
        client.create_collection = AsyncMock()
        client.delete_collection = AsyncMock()
        client.create_payload_index = AsyncMock()
        client.upsert = AsyncMock()
        client.search = AsyncMock(return_value=[])
        client.delete = AsyncMock()
        client.count = AsyncMock(return_value=MagicMock(count=0))
        client.retrieve = AsyncMock(return_value=[])
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def vector_store(self, mock_client: AsyncMock) -> QdrantVectorStore:
        """Create QdrantVectorStore with mock client."""
        store = QdrantVectorStore(host="localhost", port=6333)
        store._client = mock_client
        return store

    @pytest.mark.asyncio
    async def test_initialize(self, mock_client: AsyncMock) -> None:
        """Test initialization creates client."""
        with patch(
            "aswa_ingestion.vectorstore.qdrant.AsyncQdrantClient",
            return_value=mock_client,
        ):
            store = QdrantVectorStore(host="localhost", port=6333)
            await store.initialize()

            assert store._client is not None
            mock_client.get_collections.assert_called_once()

    @pytest.mark.asyncio
    async def test_close(self, vector_store: QdrantVectorStore) -> None:
        """Test close cleans up client."""
        await vector_store.close()
        assert vector_store._client is None

    @pytest.mark.asyncio
    async def test_create_collection(
        self, vector_store: QdrantVectorStore, mock_client: AsyncMock
    ) -> None:
        """Test collection creation."""
        from qdrant_client.http.exceptions import UnexpectedResponse

        # Collection doesn't exist
        mock_client.get_collection.side_effect = UnexpectedResponse(
            status_code=404, reason_phrase="Not found", content=b""
        )

        result = await vector_store.create_collection("test_collection", dimension=1536)

        assert result is True
        mock_client.create_collection.assert_called_once()
        # Should create payload indexes
        assert mock_client.create_payload_index.call_count >= 4

    @pytest.mark.asyncio
    async def test_create_collection_already_exists(
        self, vector_store: QdrantVectorStore, mock_client: AsyncMock
    ) -> None:
        """Test creating existing collection returns False."""
        mock_client.get_collection.return_value = MagicMock()

        result = await vector_store.create_collection("existing", dimension=1536)

        assert result is False
        mock_client.create_collection.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_collection(
        self, vector_store: QdrantVectorStore, mock_client: AsyncMock
    ) -> None:
        """Test collection deletion."""
        result = await vector_store.delete_collection("test_collection")

        assert result is True
        mock_client.delete_collection.assert_called_once_with("test_collection")

    @pytest.mark.asyncio
    async def test_collection_exists(
        self, vector_store: QdrantVectorStore, mock_client: AsyncMock
    ) -> None:
        """Test checking collection existence."""
        mock_client.get_collection.return_value = MagicMock()

        result = await vector_store.collection_exists("test_collection")

        assert result is True

    @pytest.mark.asyncio
    async def test_upsert(
        self, vector_store: QdrantVectorStore, mock_client: AsyncMock
    ) -> None:
        """Test upserting records."""
        tenant_id = uuid4()
        records = [
            VectorRecord(
                id="doc1_chunk0",
                vector=[0.1] * 1536,
                payload={"text": "Hello world"},
                tenant_id=tenant_id,
                document_id="doc1",
                chunk_index=0,
            ),
            VectorRecord(
                id="doc1_chunk1",
                vector=[0.2] * 1536,
                payload={"text": "Goodbye world"},
                tenant_id=tenant_id,
                document_id="doc1",
                chunk_index=1,
            ),
        ]

        result = await vector_store.upsert("documents", records)

        assert result == 2
        mock_client.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_batching(
        self, vector_store: QdrantVectorStore, mock_client: AsyncMock
    ) -> None:
        """Test upsert with batching."""
        vector_store._batch_size = 2
        records = [
            VectorRecord(
                id=f"doc{i}",
                vector=[0.1] * 1536,
                payload={"text": f"Text {i}"},
            )
            for i in range(5)
        ]

        result = await vector_store.upsert("documents", records)

        assert result == 5
        # Should be 3 batches: [2, 2, 1]
        assert mock_client.upsert.call_count == 3

    @pytest.mark.asyncio
    async def test_search(
        self, vector_store: QdrantVectorStore, mock_client: AsyncMock
    ) -> None:
        """Test vector search."""
        mock_client.search.return_value = [
            MagicMock(id="doc1", score=0.95, payload={"text": "Hello"}, vector=None),
            MagicMock(id="doc2", score=0.85, payload={"text": "World"}, vector=None),
        ]

        query_vector = [0.1] * 1536
        results = await vector_store.search("documents", query_vector, limit=5)

        assert len(results) == 2
        assert results[0].id == "doc1"
        assert results[0].score == 0.95
        mock_client.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_with_tenant_filter(
        self, vector_store: QdrantVectorStore, mock_client: AsyncMock
    ) -> None:
        """Test search with tenant filtering."""
        tenant_id = uuid4()
        mock_client.search.return_value = []

        await vector_store.search(
            "documents",
            [0.1] * 1536,
            tenant_id=tenant_id,
        )

        call_args = mock_client.search.call_args
        assert call_args.kwargs.get("query_filter") is not None

    @pytest.mark.asyncio
    async def test_search_with_filters(
        self, vector_store: QdrantVectorStore, mock_client: AsyncMock
    ) -> None:
        """Test search with metadata filters."""
        filters = [
            SearchFilter(field="source_type", operator=FilterOperator.EQ, value="email"),
            SearchFilter(field="importance", operator=FilterOperator.GTE, value=5),
        ]

        mock_client.search.return_value = []
        await vector_store.search("documents", [0.1] * 1536, filters=filters)

        call_args = mock_client.search.call_args
        query_filter = call_args.kwargs.get("query_filter")
        assert query_filter is not None
        assert len(query_filter.must) == 2

    @pytest.mark.asyncio
    async def test_delete_by_id(
        self, vector_store: QdrantVectorStore, mock_client: AsyncMock
    ) -> None:
        """Test deleting by ID."""
        result = await vector_store.delete("documents", ["doc1", "doc2"])

        assert result == 2
        mock_client.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_by_filter(
        self, vector_store: QdrantVectorStore, mock_client: AsyncMock
    ) -> None:
        """Test deleting by filter."""
        mock_client.count.return_value = MagicMock(count=5)

        filters = [
            SearchFilter(field="document_id", operator=FilterOperator.EQ, value="doc1")
        ]

        result = await vector_store.delete_by_filter("documents", filters)

        assert result == 5
        mock_client.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_count(
        self, vector_store: QdrantVectorStore, mock_client: AsyncMock
    ) -> None:
        """Test counting records."""
        mock_client.count.return_value = MagicMock(count=100)

        result = await vector_store.count("documents")

        assert result == 100
        mock_client.count.assert_called_once()

    @pytest.mark.asyncio
    async def test_count_with_tenant(
        self, vector_store: QdrantVectorStore, mock_client: AsyncMock
    ) -> None:
        """Test counting with tenant filter."""
        tenant_id = uuid4()
        mock_client.count.return_value = MagicMock(count=50)

        result = await vector_store.count("documents", tenant_id=tenant_id)

        assert result == 50
        call_args = mock_client.count.call_args
        assert call_args.kwargs.get("count_filter") is not None

    @pytest.mark.asyncio
    async def test_get(
        self, vector_store: QdrantVectorStore, mock_client: AsyncMock
    ) -> None:
        """Test getting records by ID."""
        mock_client.retrieve.return_value = [
            MagicMock(
                id="doc1",
                vector=[0.1] * 10,
                payload={"text": "Hello", "tenant_id": str(uuid4())},
            )
        ]

        results = await vector_store.get("documents", ["doc1"], include_vectors=True)

        assert len(results) == 1
        assert results[0].id == "doc1"

    @pytest.mark.asyncio
    async def test_health_check(
        self, vector_store: QdrantVectorStore, mock_client: AsyncMock
    ) -> None:
        """Test health check."""
        result = await vector_store.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(
        self, vector_store: QdrantVectorStore, mock_client: AsyncMock
    ) -> None:
        """Test health check on failure."""
        mock_client.get_collections.side_effect = Exception("Connection failed")

        result = await vector_store.health_check()
        assert result is False


class TestFilterConversion:
    """Tests for filter conversion logic."""

    @pytest.fixture
    def vector_store(self) -> QdrantVectorStore:
        """Create QdrantVectorStore."""
        return QdrantVectorStore(host="localhost")

    def test_convert_eq_filter(self, vector_store: QdrantVectorStore) -> None:
        """Test EQ filter conversion."""
        f = SearchFilter(field="status", operator=FilterOperator.EQ, value="active")
        condition = vector_store._convert_filter(f)

        assert condition is not None
        assert condition.key == "status"

    def test_convert_in_filter(self, vector_store: QdrantVectorStore) -> None:
        """Test IN filter conversion."""
        f = SearchFilter(
            field="category", operator=FilterOperator.IN, value=["a", "b", "c"]
        )
        condition = vector_store._convert_filter(f)

        assert condition is not None

    def test_convert_range_filter(self, vector_store: QdrantVectorStore) -> None:
        """Test range filter conversion."""
        f = SearchFilter(field="score", operator=FilterOperator.GTE, value=0.5)
        condition = vector_store._convert_filter(f)

        assert condition is not None


class TestHybridSearcher:
    """Tests for HybridSearcher."""

    @pytest.fixture
    def mock_vector_store(self) -> AsyncMock:
        """Create mock vector store."""
        store = AsyncMock()
        store.search = AsyncMock(return_value=[])
        return store

    @pytest.fixture
    def hybrid_searcher(self, mock_vector_store: AsyncMock) -> HybridSearcher:
        """Create HybridSearcher with mocks."""
        return HybridSearcher(
            vector_store=mock_vector_store,
            bm25_search_fn=None,
            vector_weight=0.7,
            bm25_weight=0.3,
        )

    @pytest.mark.asyncio
    async def test_vector_only_search(
        self, hybrid_searcher: HybridSearcher, mock_vector_store: AsyncMock
    ) -> None:
        """Test search without BM25."""
        from aswa_ingestion.vectorstore.base import SearchResult

        mock_vector_store.search.return_value = [
            SearchResult(id="doc1", score=0.9, payload={"text": "Hello"}),
            SearchResult(id="doc2", score=0.8, payload={"text": "World"}),
        ]

        results = await hybrid_searcher.search(
            "documents",
            query_text="hello world",
            query_vector=[0.1] * 1536,
            limit=5,
        )

        assert len(results) == 2
        assert results[0].id == "doc1"

    @pytest.mark.asyncio
    async def test_hybrid_search_with_bm25(
        self, mock_vector_store: AsyncMock
    ) -> None:
        """Test hybrid search with BM25."""
        from aswa_ingestion.vectorstore.base import SearchResult

        mock_vector_store.search.return_value = [
            SearchResult(id="doc1", score=0.9, payload={}),
            SearchResult(id="doc2", score=0.8, payload={}),
        ]

        def mock_bm25(query: str, limit: int, tenant_id) -> list[tuple[str, float]]:
            return [("doc2", 10.0), ("doc3", 8.0)]

        searcher = HybridSearcher(
            vector_store=mock_vector_store,
            bm25_search_fn=mock_bm25,
            vector_weight=0.5,
            bm25_weight=0.5,
        )

        results = await searcher.search(
            "documents",
            query_text="hello",
            query_vector=[0.1] * 1536,
            limit=5,
        )

        # doc2 should rank higher (appears in both)
        ids = [r.id for r in results]
        assert "doc2" in ids
        assert "doc1" in ids
        assert "doc3" in ids

    def test_rrf_fusion(self, hybrid_searcher: HybridSearcher) -> None:
        """Test RRF fusion logic."""
        from aswa_ingestion.vectorstore.base import SearchResult

        vector_results = [
            SearchResult(id="a", score=0.9, payload={}),
            SearchResult(id="b", score=0.8, payload={}),
            SearchResult(id="c", score=0.7, payload={}),
        ]

        bm25_results = [
            ("b", 10.0),
            ("d", 8.0),
            ("a", 6.0),
        ]

        results = hybrid_searcher._fuse_rrf(vector_results, bm25_results, limit=4)

        # Both a and b appear in both lists, should rank high
        ids = [r.id for r in results]
        assert len(ids) == 4
        # b ranks #1 in bm25 and #2 in vector, should be top
        assert ids[0] in ["a", "b"]


class TestReRanker:
    """Tests for ReRanker."""

    @pytest.fixture
    def reranker(self) -> ReRanker:
        """Create ReRanker."""
        return ReRanker(model_name="cross-encoder/ms-marco-MiniLM-L-6-v2")

    @pytest.mark.asyncio
    async def test_rerank_without_model(self, reranker: ReRanker) -> None:
        """Test rerank returns original when model unavailable."""
        results = [
            HybridResult(id="doc1", combined_score=0.9, payload={"text": "Hello"}),
            HybridResult(id="doc2", combined_score=0.8, payload={"text": "World"}),
        ]

        # Don't initialize model
        reranked = await reranker.rerank("query", results)

        # Should return original results
        assert len(reranked) == 2


class TestNormalizeScores:
    """Tests for score normalization."""

    def test_normalize_scores(self) -> None:
        """Test score normalization."""
        results = [
            HybridResult(id="a", combined_score=10.0),
            HybridResult(id="b", combined_score=5.0),
            HybridResult(id="c", combined_score=0.0),
        ]

        normalized = normalize_scores(results, min_score=0.0, max_score=1.0)

        assert normalized[0].combined_score == 1.0
        assert normalized[1].combined_score == 0.5
        assert normalized[2].combined_score == 0.0

    def test_normalize_same_scores(self) -> None:
        """Test normalization with same scores."""
        results = [
            HybridResult(id="a", combined_score=5.0),
            HybridResult(id="b", combined_score=5.0),
        ]

        normalized = normalize_scores(results, min_score=0.0, max_score=1.0)

        # Should return midpoint
        assert normalized[0].combined_score == 0.5
        assert normalized[1].combined_score == 0.5

    def test_normalize_empty(self) -> None:
        """Test normalization with empty list."""
        normalized = normalize_scores([])
        assert normalized == []
