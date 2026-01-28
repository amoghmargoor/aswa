"""Qdrant vector store implementation.

Provides multi-tenant vector storage using Qdrant with support for
payload indexing, filtering, and batch operations.
"""

import time
from typing import Any
from uuid import UUID

from qdrant_client import QdrantClient, AsyncQdrantClient
from qdrant_client.http import models as qdrant_models
from qdrant_client.http.exceptions import UnexpectedResponse
from pydantic import BaseModel

from aswa_common.logging import get_logger

from aswa_ingestion.config import settings
from aswa_ingestion.vectorstore.base import (
    VectorStore,
    VectorRecord,
    SearchResult,
    SearchFilter,
    FilterOperator,
)

logger = get_logger(__name__)


class QdrantMetrics(BaseModel):
    """Metrics for Qdrant operations."""

    upsert_count: int = 0
    upsert_latency_ms: float = 0
    search_count: int = 0
    search_latency_ms: float = 0
    delete_count: int = 0
    errors: int = 0


class QdrantVectorStore(VectorStore):
    """Qdrant vector database implementation.

    Features:
    - Multi-tenancy via tenant_id payload filtering
    - Automatic payload index creation for common fields
    - Batch upsert with configurable batch size
    - gRPC support for better performance
    - Metrics collection
    """

    # Default payload fields to index for filtering
    DEFAULT_INDEXED_FIELDS = [
        ("tenant_id", "keyword"),
        ("document_id", "keyword"),
        ("source_type", "keyword"),
        ("created_at", "datetime"),
    ]

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        api_key: str | None = None,
        prefer_grpc: bool | None = None,
        batch_size: int = 100,
    ) -> None:
        """Initialize Qdrant vector store.

        Args:
            host: Qdrant host
            port: Qdrant port
            api_key: Optional API key for Qdrant Cloud
            prefer_grpc: Use gRPC instead of HTTP
            batch_size: Batch size for upsert operations
        """
        self._host = host or settings.qdrant.host
        self._port = port or settings.qdrant.port
        self._api_key = api_key or settings.qdrant.api_key
        self._prefer_grpc = prefer_grpc if prefer_grpc is not None else settings.qdrant.prefer_grpc
        self._batch_size = batch_size

        self._client: AsyncQdrantClient | None = None
        self.metrics = QdrantMetrics()

        logger.info(f"QdrantVectorStore initialized: host={self._host}, port={self._port}")

    async def initialize(self) -> None:
        """Initialize async Qdrant client."""
        if self._client is not None:
            return

        self._client = AsyncQdrantClient(
            host=self._host,
            port=self._port,
            api_key=self._api_key,
            prefer_grpc=self._prefer_grpc,
        )

        # Verify connectivity
        try:
            await self._client.get_collections()
            logger.info("Qdrant connection established")
        except Exception as e:
            logger.error(f"Failed to connect to Qdrant: {e}")
            raise

    async def close(self) -> None:
        """Close Qdrant client."""
        if self._client is not None:
            await self._client.close()
            self._client = None
            logger.info("Qdrant connection closed")

    def _get_client(self) -> AsyncQdrantClient:
        """Get the async client, raising if not initialized."""
        if self._client is None:
            raise RuntimeError("QdrantVectorStore not initialized. Call initialize() first.")
        return self._client

    async def create_collection(
        self,
        name: str,
        dimension: int,
        *,
        distance_metric: str = "cosine",
        on_disk: bool = False,
    ) -> bool:
        """Create a Qdrant collection with payload indexes.

        Args:
            name: Collection name
            dimension: Vector dimension
            distance_metric: Distance metric (cosine, euclid, dot)
            on_disk: Store vectors on disk for large collections

        Returns:
            True if created, False if already exists
        """
        client = self._get_client()

        # Check if exists
        try:
            await client.get_collection(name)
            logger.info(f"Collection '{name}' already exists")
            return False
        except UnexpectedResponse:
            pass  # Collection doesn't exist

        # Map distance metric
        distance_map = {
            "cosine": qdrant_models.Distance.COSINE,
            "euclid": qdrant_models.Distance.EUCLID,
            "dot": qdrant_models.Distance.DOT,
        }
        distance = distance_map.get(distance_metric, qdrant_models.Distance.COSINE)

        # Create collection
        await client.create_collection(
            collection_name=name,
            vectors_config=qdrant_models.VectorParams(
                size=dimension,
                distance=distance,
                on_disk=on_disk,
            ),
            optimizers_config=qdrant_models.OptimizersConfigDiff(
                indexing_threshold=20000,
            ),
        )

        # Create payload indexes for common filter fields
        for field_name, field_type in self.DEFAULT_INDEXED_FIELDS:
            await self._create_payload_index(name, field_name, field_type)

        logger.info(f"Created collection '{name}' with dimension {dimension}")
        return True

    async def _create_payload_index(
        self,
        collection: str,
        field_name: str,
        field_type: str,
    ) -> None:
        """Create payload index for efficient filtering.

        Args:
            collection: Collection name
            field_name: Field to index
            field_type: Type of index (keyword, integer, float, datetime, text)
        """
        client = self._get_client()

        schema_map = {
            "keyword": qdrant_models.PayloadSchemaType.KEYWORD,
            "integer": qdrant_models.PayloadSchemaType.INTEGER,
            "float": qdrant_models.PayloadSchemaType.FLOAT,
            "datetime": qdrant_models.PayloadSchemaType.DATETIME,
            "text": qdrant_models.PayloadSchemaType.TEXT,
        }

        schema_type = schema_map.get(field_type, qdrant_models.PayloadSchemaType.KEYWORD)

        try:
            await client.create_payload_index(
                collection_name=collection,
                field_name=field_name,
                field_schema=schema_type,
            )
            logger.debug(f"Created index on {collection}.{field_name}")
        except Exception as e:
            # Index may already exist
            logger.debug(f"Index creation for {field_name} skipped: {e}")

    async def delete_collection(self, name: str) -> bool:
        """Delete a Qdrant collection.

        Args:
            name: Collection name

        Returns:
            True if deleted, False if not found
        """
        client = self._get_client()

        try:
            await client.delete_collection(name)
            logger.info(f"Deleted collection '{name}'")
            return True
        except UnexpectedResponse:
            logger.warning(f"Collection '{name}' not found for deletion")
            return False

    async def collection_exists(self, name: str) -> bool:
        """Check if collection exists.

        Args:
            name: Collection name

        Returns:
            True if exists
        """
        client = self._get_client()

        try:
            await client.get_collection(name)
            return True
        except UnexpectedResponse:
            return False

    async def upsert(
        self,
        collection: str,
        records: list[VectorRecord],
        *,
        wait: bool = True,
    ) -> int:
        """Insert or update vectors in batches.

        Args:
            collection: Collection name
            records: Records to upsert
            wait: Wait for operation to complete

        Returns:
            Number of records upserted
        """
        if not records:
            return 0

        client = self._get_client()
        start_time = time.time()
        total_upserted = 0

        # Process in batches
        for i in range(0, len(records), self._batch_size):
            batch = records[i : i + self._batch_size]

            points = [
                qdrant_models.PointStruct(
                    id=record.id,
                    vector=record.vector,
                    payload=self._build_payload(record),
                )
                for record in batch
            ]

            try:
                await client.upsert(
                    collection_name=collection,
                    points=points,
                    wait=wait,
                )
                total_upserted += len(batch)
            except Exception as e:
                self.metrics.errors += 1
                logger.error(f"Upsert batch failed: {e}")
                raise

        elapsed_ms = (time.time() - start_time) * 1000
        self.metrics.upsert_count += total_upserted
        self.metrics.upsert_latency_ms += elapsed_ms

        logger.debug(f"Upserted {total_upserted} records in {elapsed_ms:.0f}ms")
        return total_upserted

    def _build_payload(self, record: VectorRecord) -> dict[str, Any]:
        """Build Qdrant payload from VectorRecord.

        Merges record metadata with standard fields for indexing.
        """
        payload = dict(record.payload)

        # Add standard fields if present
        if record.tenant_id:
            payload["tenant_id"] = str(record.tenant_id)
        if record.document_id:
            payload["document_id"] = record.document_id
        if record.chunk_index is not None:
            payload["chunk_index"] = record.chunk_index

        return payload

    async def search(
        self,
        collection: str,
        query_vector: list[float],
        *,
        limit: int = 10,
        filters: list[SearchFilter] | None = None,
        tenant_id: UUID | None = None,
        include_vectors: bool = False,
        score_threshold: float | None = None,
    ) -> list[SearchResult]:
        """Search for similar vectors with filtering.

        Args:
            collection: Collection name
            query_vector: Query embedding
            limit: Maximum results
            filters: Metadata filters
            tenant_id: Filter by tenant
            include_vectors: Include vectors in results
            score_threshold: Minimum score threshold

        Returns:
            Sorted search results
        """
        client = self._get_client()
        start_time = time.time()

        # Build filter
        query_filter = self._build_filter(filters, tenant_id)

        try:
            results = await client.search(
                collection_name=collection,
                query_vector=query_vector,
                limit=limit,
                query_filter=query_filter,
                with_vectors=include_vectors,
                score_threshold=score_threshold,
            )
        except Exception as e:
            self.metrics.errors += 1
            logger.error(f"Search failed: {e}")
            raise

        elapsed_ms = (time.time() - start_time) * 1000
        self.metrics.search_count += 1
        self.metrics.search_latency_ms += elapsed_ms

        logger.debug(f"Search returned {len(results)} results in {elapsed_ms:.0f}ms")

        return [
            SearchResult(
                id=str(hit.id),
                score=hit.score,
                payload=dict(hit.payload) if hit.payload else {},
                vector=hit.vector if include_vectors and hit.vector else None,
            )
            for hit in results
        ]

    def _build_filter(
        self,
        filters: list[SearchFilter] | None,
        tenant_id: UUID | None,
    ) -> qdrant_models.Filter | None:
        """Build Qdrant filter from SearchFilter list.

        Args:
            filters: Application filters
            tenant_id: Tenant ID to filter by

        Returns:
            Qdrant Filter or None
        """
        conditions: list[qdrant_models.Condition] = []

        # Add tenant filter
        if tenant_id:
            conditions.append(
                qdrant_models.FieldCondition(
                    key="tenant_id",
                    match=qdrant_models.MatchValue(value=str(tenant_id)),
                )
            )

        # Convert application filters
        if filters:
            for f in filters:
                condition = self._convert_filter(f)
                if condition:
                    conditions.append(condition)

        if not conditions:
            return None

        return qdrant_models.Filter(must=conditions)

    def _convert_filter(self, f: SearchFilter) -> qdrant_models.Condition | None:
        """Convert a SearchFilter to Qdrant condition.

        Args:
            f: SearchFilter to convert

        Returns:
            Qdrant Condition or None
        """
        if f.operator == FilterOperator.EQ:
            return qdrant_models.FieldCondition(
                key=f.field,
                match=qdrant_models.MatchValue(value=f.value),
            )

        elif f.operator == FilterOperator.NE:
            return qdrant_models.FieldCondition(
                key=f.field,
                match=qdrant_models.MatchExcept(**{"except": [f.value]}),
            )

        elif f.operator == FilterOperator.IN:
            return qdrant_models.FieldCondition(
                key=f.field,
                match=qdrant_models.MatchAny(any=f.value),
            )

        elif f.operator == FilterOperator.NOT_IN:
            return qdrant_models.FieldCondition(
                key=f.field,
                match=qdrant_models.MatchExcept(**{"except": f.value}),
            )

        elif f.operator == FilterOperator.GT:
            return qdrant_models.FieldCondition(
                key=f.field,
                range=qdrant_models.Range(gt=f.value),
            )

        elif f.operator == FilterOperator.GTE:
            return qdrant_models.FieldCondition(
                key=f.field,
                range=qdrant_models.Range(gte=f.value),
            )

        elif f.operator == FilterOperator.LT:
            return qdrant_models.FieldCondition(
                key=f.field,
                range=qdrant_models.Range(lt=f.value),
            )

        elif f.operator == FilterOperator.LTE:
            return qdrant_models.FieldCondition(
                key=f.field,
                range=qdrant_models.Range(lte=f.value),
            )

        elif f.operator == FilterOperator.CONTAINS:
            return qdrant_models.FieldCondition(
                key=f.field,
                match=qdrant_models.MatchText(text=f.value),
            )

        elif f.operator == FilterOperator.HAS_ANY:
            return qdrant_models.FieldCondition(
                key=f.field,
                match=qdrant_models.MatchAny(any=f.value),
            )

        logger.warning(f"Unknown filter operator: {f.operator}")
        return None

    async def delete(
        self,
        collection: str,
        ids: list[str],
    ) -> int:
        """Delete records by ID.

        Args:
            collection: Collection name
            ids: Record IDs to delete

        Returns:
            Number of records deleted
        """
        if not ids:
            return 0

        client = self._get_client()

        try:
            result = await client.delete(
                collection_name=collection,
                points_selector=qdrant_models.PointIdsList(points=ids),
            )
            self.metrics.delete_count += len(ids)
            logger.debug(f"Deleted {len(ids)} records")
            return len(ids)
        except Exception as e:
            self.metrics.errors += 1
            logger.error(f"Delete failed: {e}")
            raise

    async def delete_by_filter(
        self,
        collection: str,
        filters: list[SearchFilter],
        *,
        tenant_id: UUID | None = None,
    ) -> int:
        """Delete records matching filter.

        Args:
            collection: Collection name
            filters: Filter conditions
            tenant_id: Optional tenant filter

        Returns:
            Number of records deleted (estimated)
        """
        client = self._get_client()
        query_filter = self._build_filter(filters, tenant_id)

        if not query_filter:
            logger.warning("No filter provided for delete_by_filter")
            return 0

        # Count before delete for return value
        count_before = await self.count(collection, filters=filters, tenant_id=tenant_id)

        try:
            await client.delete(
                collection_name=collection,
                points_selector=qdrant_models.FilterSelector(filter=query_filter),
            )
            self.metrics.delete_count += count_before
            logger.debug(f"Deleted ~{count_before} records by filter")
            return count_before
        except Exception as e:
            self.metrics.errors += 1
            logger.error(f"Delete by filter failed: {e}")
            raise

    async def count(
        self,
        collection: str,
        *,
        filters: list[SearchFilter] | None = None,
        tenant_id: UUID | None = None,
    ) -> int:
        """Count records matching filter.

        Args:
            collection: Collection name
            filters: Optional filters
            tenant_id: Optional tenant filter

        Returns:
            Number of matching records
        """
        client = self._get_client()
        query_filter = self._build_filter(filters, tenant_id)

        try:
            result = await client.count(
                collection_name=collection,
                count_filter=query_filter,
                exact=True,
            )
            return result.count
        except Exception as e:
            self.metrics.errors += 1
            logger.error(f"Count failed: {e}")
            raise

    async def get(
        self,
        collection: str,
        ids: list[str],
        *,
        include_vectors: bool = False,
    ) -> list[VectorRecord]:
        """Get records by ID.

        Args:
            collection: Collection name
            ids: Record IDs
            include_vectors: Include vectors

        Returns:
            Matching records
        """
        if not ids:
            return []

        client = self._get_client()

        try:
            results = await client.retrieve(
                collection_name=collection,
                ids=ids,
                with_vectors=include_vectors,
            )

            records = []
            for point in results:
                payload = dict(point.payload) if point.payload else {}
                records.append(
                    VectorRecord(
                        id=str(point.id),
                        vector=point.vector if include_vectors and point.vector else [],
                        payload=payload,
                        tenant_id=UUID(payload.get("tenant_id")) if payload.get("tenant_id") else None,
                        document_id=payload.get("document_id"),
                        chunk_index=payload.get("chunk_index", 0),
                    )
                )
            return records
        except Exception as e:
            self.metrics.errors += 1
            logger.error(f"Get failed: {e}")
            raise

    async def health_check(self) -> bool:
        """Check Qdrant health.

        Returns:
            True if healthy
        """
        try:
            client = self._get_client()
            await client.get_collections()
            return True
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False
