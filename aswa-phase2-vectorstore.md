# ASWA Phase 2.3: Vector Store Integration

## Task 2.3: Qdrant Vector Store

### Subtask 2.3.1: Qdrant Client Wrapper

**Claude Code Prompt:**
```
Create the Qdrant vector store integration at /services/ingestion-service/src/aswa_ingestion/vectorstore/.

1. /services/ingestion-service/src/aswa_ingestion/vectorstore/__init__.py:
from .qdrant import QdrantVectorStore
from .base import VectorStore, VectorRecord, SearchResult
__all__ = ["QdrantVectorStore", "VectorStore", "VectorRecord", "SearchResult"]

2. /services/ingestion-service/src/aswa_ingestion/vectorstore/base.py:
from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Any

class VectorRecord(BaseModel):
    """Record to store in vector database."""
    id: str
    vector: list[float]
    payload: dict[str, Any]
    
class SearchResult(BaseModel):
    """Result from vector search."""
    id: str
    score: float
    payload: dict[str, Any]

class VectorStore(ABC):
    """Abstract base class for vector store implementations."""
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize connection and create collections if needed."""
        ...
    
    @abstractmethod
    async def create_collection(
        self, 
        name: str, 
        vector_size: int,
        distance: str = "cosine"
    ) -> None:
        """Create a new collection."""
        ...
    
    @abstractmethod
    async def collection_exists(self, name: str) -> bool:
        """Check if collection exists."""
        ...
    
    @abstractmethod
    async def upsert(
        self, 
        collection: str, 
        records: list[VectorRecord],
        wait: bool = True
    ) -> int:
        """Upsert records into collection. Returns count of upserted records."""
        ...
    
    @abstractmethod
    async def search(
        self,
        collection: str,
        query_vector: list[float],
        limit: int = 10,
        score_threshold: float | None = None,
        filters: dict[str, Any] | None = None
    ) -> list[SearchResult]:
        """Search for similar vectors."""
        ...
    
    @abstractmethod
    async def get_by_ids(
        self,
        collection: str,
        ids: list[str]
    ) -> list[VectorRecord]:
        """Retrieve records by IDs."""
        ...
    
    @abstractmethod
    async def delete(
        self, 
        collection: str, 
        ids: list[str]
    ) -> int:
        """Delete records by IDs. Returns count of deleted records."""
        ...
    
    @abstractmethod
    async def delete_by_filter(
        self, 
        collection: str, 
        filters: dict[str, Any]
    ) -> int:
        """Delete records matching filter. Returns count of deleted records."""
        ...
    
    @abstractmethod
    async def count(
        self,
        collection: str,
        filters: dict[str, Any] | None = None
    ) -> int:
        """Count records in collection, optionally filtered."""
        ...
    
    @abstractmethod
    async def close(self) -> None:
        """Close connection."""
        ...

3. /services/ingestion-service/src/aswa_ingestion/vectorstore/qdrant.py:
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    VectorParams, Distance, PointStruct,
    Filter, FieldCondition, MatchValue, MatchAny, Range,
    UpdateStatus, PayloadSchemaType, CreateAliasOperation,
    OptimizersConfigDiff, HnswConfigDiff
)
from qdrant_client.http.exceptions import UnexpectedResponse
import structlog
from aswa_common.metrics import MetricsRegistry, timed
from aswa_common.exceptions import AswaError, ErrorCode
from .base import VectorStore, VectorRecord, SearchResult

logger = structlog.get_logger()

class QdrantVectorStore(VectorStore):
    """Qdrant vector database integration with multi-tenancy support."""
    
    DISTANCE_MAP = {
        "cosine": Distance.COSINE,
        "euclidean": Distance.EUCLID,
        "dot": Distance.DOT
    }
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6333,
        grpc_port: int = 6334,
        api_key: str | None = None,
        https: bool = False,
        prefer_grpc: bool = True,
        timeout: float = 30.0
    ):
        self.host = host
        self.port = port
        self.grpc_port = grpc_port
        self.api_key = api_key
        self.https = https
        self.prefer_grpc = prefer_grpc
        self.timeout = timeout
        self.client: AsyncQdrantClient | None = None
        self._metrics = MetricsRegistry("qdrant_vectorstore")
        
        # Define metrics
        self._upsert_counter = self._metrics.counter(
            "vectors_upserted_total",
            "Total vectors upserted",
            ["collection"]
        )
        self._search_histogram = self._metrics.histogram(
            "search_duration_seconds",
            "Vector search duration",
            ["collection"]
        )
        self._delete_counter = self._metrics.counter(
            "vectors_deleted_total",
            "Total vectors deleted",
            ["collection"]
        )
    
    async def initialize(self) -> None:
        """Initialize Qdrant client connection."""
        try:
            self.client = AsyncQdrantClient(
                host=self.host,
                port=self.port,
                grpc_port=self.grpc_port,
                api_key=self.api_key,
                https=self.https,
                prefer_grpc=self.prefer_grpc,
                timeout=self.timeout
            )
            # Test connection
            await self.client.get_collections()
            logger.info("Qdrant connection established", host=self.host, port=self.port)
        except Exception as e:
            logger.error("Failed to connect to Qdrant", error=str(e))
            raise AswaError(ErrorCode.EXTERNAL_SERVICE_ERROR, f"Qdrant connection failed: {e}")
    
    async def create_collection(
        self,
        name: str,
        vector_size: int,
        distance: str = "cosine"
    ) -> None:
        """Create collection with optimized settings for production."""
        if await self.collection_exists(name):
            logger.info("Collection already exists", collection=name)
            return
        
        try:
            await self.client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=self.DISTANCE_MAP.get(distance, Distance.COSINE)
                ),
                # Optimized settings for production
                hnsw_config=HnswConfigDiff(
                    m=16,  # Number of edges per node
                    ef_construct=100,  # Construction time/accuracy tradeoff
                    full_scan_threshold=10000  # Use brute force below this
                ),
                optimizers_config=OptimizersConfigDiff(
                    indexing_threshold=20000,  # Start indexing after this many vectors
                    memmap_threshold=50000  # Use mmap after this many vectors
                ),
                on_disk_payload=True  # Store payload on disk for large collections
            )
            
            # Create payload indexes for filtering
            await self._create_payload_indexes(name)
            
            logger.info("Collection created", collection=name, vector_size=vector_size)
        except Exception as e:
            logger.error("Failed to create collection", collection=name, error=str(e))
            raise AswaError(ErrorCode.EXTERNAL_SERVICE_ERROR, f"Failed to create collection: {e}")
    
    async def _create_payload_indexes(self, collection: str) -> None:
        """Create indexes on commonly filtered payload fields."""
        index_fields = [
            ("tenant_id", PayloadSchemaType.KEYWORD),
            ("document_id", PayloadSchemaType.KEYWORD),
            ("source_type", PayloadSchemaType.KEYWORD),
            ("content_type", PayloadSchemaType.KEYWORD),
            ("created_at", PayloadSchemaType.DATETIME),
        ]
        
        for field_name, field_type in index_fields:
            try:
                await self.client.create_payload_index(
                    collection_name=collection,
                    field_name=field_name,
                    field_schema=field_type
                )
            except Exception as e:
                # Index might already exist
                logger.debug("Payload index creation", field=field_name, result=str(e))
    
    async def collection_exists(self, name: str) -> bool:
        try:
            await self.client.get_collection(name)
            return True
        except UnexpectedResponse:
            return False
    
    async def upsert(
        self,
        collection: str,
        records: list[VectorRecord],
        wait: bool = True,
        batch_size: int = 100
    ) -> int:
        """Upsert records in batches."""
        if not records:
            return 0
        
        total_upserted = 0
        
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            points = [
                PointStruct(
                    id=record.id,
                    vector=record.vector,
                    payload=record.payload
                )
                for record in batch
            ]
            
            try:
                result = await self.client.upsert(
                    collection_name=collection,
                    points=points,
                    wait=wait
                )
                
                if result.status == UpdateStatus.COMPLETED:
                    total_upserted += len(batch)
                    self._upsert_counter.labels(collection=collection).inc(len(batch))
                    
            except Exception as e:
                logger.error("Upsert failed", collection=collection, batch_start=i, error=str(e))
                raise AswaError(ErrorCode.EXTERNAL_SERVICE_ERROR, f"Upsert failed: {e}")
        
        logger.info("Upsert completed", collection=collection, count=total_upserted)
        return total_upserted
    
    async def search(
        self,
        collection: str,
        query_vector: list[float],
        limit: int = 10,
        score_threshold: float | None = None,
        filters: dict[str, Any] | None = None
    ) -> list[SearchResult]:
        """Search for similar vectors with optional filtering."""
        import time
        start = time.monotonic()
        
        try:
            # Build filter
            query_filter = self._build_filter(filters) if filters else None
            
            results = await self.client.search(
                collection_name=collection,
                query_vector=query_vector,
                limit=limit,
                score_threshold=score_threshold,
                query_filter=query_filter,
                with_payload=True
            )
            
            duration = time.monotonic() - start
            self._search_histogram.labels(collection=collection).observe(duration)
            
            return [
                SearchResult(
                    id=str(point.id),
                    score=point.score,
                    payload=point.payload or {}
                )
                for point in results
            ]
            
        except Exception as e:
            logger.error("Search failed", collection=collection, error=str(e))
            raise AswaError(ErrorCode.EXTERNAL_SERVICE_ERROR, f"Search failed: {e}")
    
    def _build_filter(self, filters: dict[str, Any]) -> Filter:
        """Build Qdrant filter from dict specification."""
        must_conditions = []
        
        for key, value in filters.items():
            if isinstance(value, list):
                # Match any in list
                must_conditions.append(
                    FieldCondition(key=key, match=MatchAny(any=value))
                )
            elif isinstance(value, dict):
                # Range filter: {"gte": x, "lte": y}
                must_conditions.append(
                    FieldCondition(key=key, range=Range(**value))
                )
            else:
                # Exact match
                must_conditions.append(
                    FieldCondition(key=key, match=MatchValue(value=value))
                )
        
        return Filter(must=must_conditions)
    
    async def get_by_ids(
        self,
        collection: str,
        ids: list[str]
    ) -> list[VectorRecord]:
        """Retrieve records by IDs."""
        try:
            points = await self.client.retrieve(
                collection_name=collection,
                ids=ids,
                with_payload=True,
                with_vectors=True
            )
            
            return [
                VectorRecord(
                    id=str(point.id),
                    vector=point.vector,
                    payload=point.payload or {}
                )
                for point in points
            ]
        except Exception as e:
            logger.error("Retrieve failed", collection=collection, error=str(e))
            raise AswaError(ErrorCode.EXTERNAL_SERVICE_ERROR, f"Retrieve failed: {e}")
    
    async def delete(
        self,
        collection: str,
        ids: list[str]
    ) -> int:
        """Delete records by IDs."""
        if not ids:
            return 0
        
        try:
            result = await self.client.delete(
                collection_name=collection,
                points_selector=ids,
                wait=True
            )
            
            if result.status == UpdateStatus.COMPLETED:
                self._delete_counter.labels(collection=collection).inc(len(ids))
                return len(ids)
            return 0
            
        except Exception as e:
            logger.error("Delete failed", collection=collection, error=str(e))
            raise AswaError(ErrorCode.EXTERNAL_SERVICE_ERROR, f"Delete failed: {e}")
    
    async def delete_by_filter(
        self,
        collection: str,
        filters: dict[str, Any]
    ) -> int:
        """Delete records matching filter."""
        try:
            query_filter = self._build_filter(filters)
            
            # First count matching records
            count_before = await self.count(collection, filters)
            
            result = await self.client.delete(
                collection_name=collection,
                points_selector=query_filter,
                wait=True
            )
            
            if result.status == UpdateStatus.COMPLETED:
                self._delete_counter.labels(collection=collection).inc(count_before)
                return count_before
            return 0
            
        except Exception as e:
            logger.error("Delete by filter failed", collection=collection, error=str(e))
            raise AswaError(ErrorCode.EXTERNAL_SERVICE_ERROR, f"Delete by filter failed: {e}")
    
    async def count(
        self,
        collection: str,
        filters: dict[str, Any] | None = None
    ) -> int:
        """Count records in collection."""
        try:
            if filters:
                result = await self.client.count(
                    collection_name=collection,
                    count_filter=self._build_filter(filters),
                    exact=True
                )
            else:
                result = await self.client.count(
                    collection_name=collection,
                    exact=True
                )
            return result.count
        except Exception as e:
            logger.error("Count failed", collection=collection, error=str(e))
            return 0
    
    async def close(self) -> None:
        """Close Qdrant client."""
        if self.client:
            await self.client.close()
            logger.info("Qdrant connection closed")

4. /services/ingestion-service/tests/vectorstore/test_qdrant.py:
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aswa_ingestion.vectorstore.qdrant import QdrantVectorStore
from aswa_ingestion.vectorstore.base import VectorRecord, SearchResult

@pytest.fixture
def mock_qdrant_client():
    with patch("aswa_ingestion.vectorstore.qdrant.AsyncQdrantClient") as mock:
        client = AsyncMock()
        mock.return_value = client
        yield client

@pytest.fixture
async def vector_store(mock_qdrant_client):
    store = QdrantVectorStore(host="localhost", port=6333)
    await store.initialize()
    return store

class TestQdrantVectorStore:
    
    @pytest.mark.asyncio
    async def test_initialize_success(self, mock_qdrant_client):
        mock_qdrant_client.get_collections = AsyncMock(return_value=[])
        
        store = QdrantVectorStore()
        await store.initialize()
        
        mock_qdrant_client.get_collections.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_collection(self, vector_store, mock_qdrant_client):
        mock_qdrant_client.get_collection = AsyncMock(side_effect=Exception("Not found"))
        mock_qdrant_client.create_collection = AsyncMock()
        mock_qdrant_client.create_payload_index = AsyncMock()
        
        await vector_store.create_collection("test_collection", 1536)
        
        mock_qdrant_client.create_collection.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_upsert_records(self, vector_store, mock_qdrant_client):
        mock_qdrant_client.upsert = AsyncMock(
            return_value=MagicMock(status="completed")
        )
        
        records = [
            VectorRecord(id="1", vector=[0.1] * 1536, payload={"tenant_id": "t1"}),
            VectorRecord(id="2", vector=[0.2] * 1536, payload={"tenant_id": "t1"})
        ]
        
        count = await vector_store.upsert("test_collection", records)
        
        assert count == 2
        mock_qdrant_client.upsert.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_search_with_filters(self, vector_store, mock_qdrant_client):
        mock_qdrant_client.search = AsyncMock(return_value=[
            MagicMock(id="1", score=0.95, payload={"content": "test"})
        ])
        
        results = await vector_store.search(
            collection="test_collection",
            query_vector=[0.1] * 1536,
            limit=10,
            filters={"tenant_id": "t1"}
        )
        
        assert len(results) == 1
        assert results[0].score == 0.95
    
    @pytest.mark.asyncio
    async def test_delete_by_ids(self, vector_store, mock_qdrant_client):
        mock_qdrant_client.delete = AsyncMock(
            return_value=MagicMock(status="completed")
        )
        
        count = await vector_store.delete("test_collection", ["1", "2"])
        
        assert count == 2
    
    @pytest.mark.asyncio
    async def test_delete_by_filter(self, vector_store, mock_qdrant_client):
        mock_qdrant_client.count = AsyncMock(return_value=MagicMock(count=5))
        mock_qdrant_client.delete = AsyncMock(
            return_value=MagicMock(status="completed")
        )
        
        count = await vector_store.delete_by_filter(
            "test_collection",
            {"document_id": "doc1"}
        )
        
        assert count == 5
    
    @pytest.mark.asyncio
    async def test_build_filter_exact_match(self, vector_store):
        filter_obj = vector_store._build_filter({"tenant_id": "t1"})
        
        assert len(filter_obj.must) == 1
        assert filter_obj.must[0].key == "tenant_id"
    
    @pytest.mark.asyncio
    async def test_build_filter_list_match(self, vector_store):
        filter_obj = vector_store._build_filter({
            "source_type": ["gmail", "slack"]
        })
        
        assert len(filter_obj.must) == 1
    
    @pytest.mark.asyncio
    async def test_build_filter_range(self, vector_store):
        filter_obj = vector_store._build_filter({
            "confidence": {"gte": 0.5, "lte": 1.0}
        })
        
        assert len(filter_obj.must) == 1

Add integration test with Testcontainers Qdrant in separate file.
```

---

### Subtask 2.3.2: Hybrid Search Implementation

**Claude Code Prompt:**
```
Create hybrid search (vector + BM25) at /services/ingestion-service/src/aswa_ingestion/vectorstore/hybrid.py.

from dataclasses import dataclass
from typing import Callable
import numpy as np

@dataclass
class HybridSearchResult:
    """Combined result from hybrid search."""
    id: str
    vector_score: float | None
    bm25_score: float | None
    combined_score: float
    payload: dict

class HybridSearcher:
    """
    Combines vector similarity search with BM25 keyword search
    using Reciprocal Rank Fusion (RRF).
    """
    
    def __init__(
        self,
        vector_store: VectorStore,
        db_session: AsyncSession,
        rrf_k: int = 60  # RRF constant, typically 60
    ):
        self.vector_store = vector_store
        self.db = db_session
        self.rrf_k = rrf_k
    
    async def search(
        self,
        collection: str,
        query: str,
        query_vector: list[float],
        tenant_id: UUID,
        limit: int = 10,
        vector_weight: float = 0.5,
        bm25_weight: float = 0.5,
        filters: dict | None = None
    ) -> list[HybridSearchResult]:
        """
        Perform hybrid search combining vector and BM25 results.
        
        Args:
            collection: Vector collection name
            query: Text query for BM25
            query_vector: Embedded query vector
            tenant_id: Tenant ID for filtering
            limit: Number of results to return
            vector_weight: Weight for vector search (0-1)
            bm25_weight: Weight for BM25 search (0-1)
            filters: Additional filters for vector search
            
        Returns:
            List of HybridSearchResult sorted by combined score
        """
        # Fetch more candidates than needed for fusion
        candidate_limit = limit * 3
        
        # Parallel execution of both searches
        vector_task = self._vector_search(
            collection, query_vector, candidate_limit, tenant_id, filters
        )
        bm25_task = self._bm25_search(query, candidate_limit, tenant_id)
        
        vector_results, bm25_results = await asyncio.gather(vector_task, bm25_task)
        
        # Fuse results using RRF
        fused = self._reciprocal_rank_fusion(
            vector_results,
            bm25_results,
            vector_weight,
            bm25_weight
        )
        
        return fused[:limit]
    
    async def _vector_search(
        self,
        collection: str,
        query_vector: list[float],
        limit: int,
        tenant_id: UUID,
        filters: dict | None
    ) -> list[tuple[str, float, dict]]:
        """Perform vector similarity search."""
        search_filters = {"tenant_id": str(tenant_id)}
        if filters:
            search_filters.update(filters)
        
        results = await self.vector_store.search(
            collection=collection,
            query_vector=query_vector,
            limit=limit,
            filters=search_filters
        )
        
        return [(r.id, r.score, r.payload) for r in results]
    
    async def _bm25_search(
        self,
        query: str,
        limit: int,
        tenant_id: UUID
    ) -> list[tuple[str, float, dict]]:
        """Perform BM25 full-text search using PostgreSQL."""
        # Use PostgreSQL full-text search with ts_rank_cd
        sql = """
            SELECT 
                dc.vector_id,
                ts_rank_cd(
                    to_tsvector('english', dc.content),
                    plainto_tsquery('english', :query)
                ) as rank,
                dc.content,
                dc.metadata,
                d.title,
                d.source_metadata
            FROM document_chunks dc
            JOIN documents d ON dc.document_id = d.id
            WHERE d.tenant_id = :tenant_id
              AND dc.vector_id IS NOT NULL
              AND to_tsvector('english', dc.content) @@ plainto_tsquery('english', :query)
            ORDER BY rank DESC
            LIMIT :limit
        """
        
        result = await self.db.execute(
            text(sql),
            {"query": query, "tenant_id": str(tenant_id), "limit": limit}
        )
        
        rows = result.fetchall()
        return [
            (
                row.vector_id,
                float(row.rank),
                {
                    "content": row.content,
                    "title": row.title,
                    "metadata": row.metadata,
                    "source_metadata": row.source_metadata
                }
            )
            for row in rows
        ]
    
    def _reciprocal_rank_fusion(
        self,
        vector_results: list[tuple[str, float, dict]],
        bm25_results: list[tuple[str, float, dict]],
        vector_weight: float,
        bm25_weight: float
    ) -> list[HybridSearchResult]:
        """
        Combine results using Reciprocal Rank Fusion.
        
        RRF score = sum(weight / (k + rank)) for each result list
        """
        scores: dict[str, dict] = {}
        
        # Process vector results
        for rank, (doc_id, score, payload) in enumerate(vector_results, 1):
            if doc_id not in scores:
                scores[doc_id] = {
                    "vector_score": None,
                    "bm25_score": None,
                    "rrf_score": 0.0,
                    "payload": payload
                }
            scores[doc_id]["vector_score"] = score
            scores[doc_id]["rrf_score"] += vector_weight / (self.rrf_k + rank)
        
        # Process BM25 results
        for rank, (doc_id, score, payload) in enumerate(bm25_results, 1):
            if doc_id not in scores:
                scores[doc_id] = {
                    "vector_score": None,
                    "bm25_score": None,
                    "rrf_score": 0.0,
                    "payload": payload
                }
            scores[doc_id]["bm25_score"] = score
            scores[doc_id]["rrf_score"] += bm25_weight / (self.rrf_k + rank)
            # Merge payloads if needed
            if scores[doc_id]["payload"] != payload:
                scores[doc_id]["payload"].update(payload)
        
        # Sort by RRF score
        sorted_results = sorted(
            scores.items(),
            key=lambda x: x[1]["rrf_score"],
            reverse=True
        )
        
        return [
            HybridSearchResult(
                id=doc_id,
                vector_score=data["vector_score"],
                bm25_score=data["bm25_score"],
                combined_score=data["rrf_score"],
                payload=data["payload"]
            )
            for doc_id, data in sorted_results
        ]

class ReRanker:
    """
    Cross-encoder reranker for improving search quality.
    Uses a cross-encoder model to rerank top-k results.
    """
    
    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-v2-m3",
        device: str = "cpu",
        batch_size: int = 32
    ):
        self.model_name = model_name
        self.device = device
        self.batch_size = batch_size
        self._model = None
    
    async def initialize(self) -> None:
        """Load the reranker model."""
        from sentence_transformers import CrossEncoder
        self._model = CrossEncoder(self.model_name, device=self.device)
        logger.info("Reranker model loaded", model=self.model_name)
    
    async def rerank(
        self,
        query: str,
        results: list[HybridSearchResult],
        top_k: int | None = None
    ) -> list[HybridSearchResult]:
        """
        Rerank results using cross-encoder.
        
        Args:
            query: Original search query
            results: Results from hybrid search
            top_k: Number of results to return (default: all)
            
        Returns:
            Reranked results with updated scores
        """
        if not results:
            return []
        
        # Prepare pairs for cross-encoder
        pairs = [
            (query, r.payload.get("content", ""))
            for r in results
        ]
        
        # Score with cross-encoder (run in thread pool for CPU model)
        loop = asyncio.get_event_loop()
        scores = await loop.run_in_executor(
            None,
            lambda: self._model.predict(pairs, batch_size=self.batch_size)
        )
        
        # Update scores and sort
        reranked = []
        for result, score in zip(results, scores):
            reranked.append(HybridSearchResult(
                id=result.id,
                vector_score=result.vector_score,
                bm25_score=result.bm25_score,
                combined_score=float(score),  # Replace with reranker score
                payload=result.payload
            ))
        
        reranked.sort(key=lambda x: x.combined_score, reverse=True)
        
        if top_k:
            return reranked[:top_k]
        return reranked

Create /services/ingestion-service/tests/vectorstore/test_hybrid.py:
- Test RRF fusion algorithm with known inputs/outputs
- Test vector-only search (bm25_weight=0)
- Test bm25-only search (vector_weight=0)
- Test reranker with mocked model
- Test empty results handling
```