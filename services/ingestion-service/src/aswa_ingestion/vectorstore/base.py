"""Abstract base class for vector store implementations.

Provides a unified interface for vector database operations
with support for multi-tenancy, filtering, and batch operations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID


class FilterOperator(str, Enum):
    """Operators for metadata filtering."""

    EQ = "eq"  # Equal
    NE = "ne"  # Not equal
    GT = "gt"  # Greater than
    GTE = "gte"  # Greater than or equal
    LT = "lt"  # Less than
    LTE = "lte"  # Less than or equal
    IN = "in"  # In list
    NOT_IN = "not_in"  # Not in list
    CONTAINS = "contains"  # String contains
    HAS_ANY = "has_any"  # Array has any of values


@dataclass
class SearchFilter:
    """Filter condition for vector search.

    Attributes:
        field: Metadata field name to filter on
        operator: Filter operator
        value: Value to compare against
    """

    field: str
    operator: FilterOperator
    value: Any


@dataclass
class VectorRecord:
    """Record to store in vector database.

    Attributes:
        id: Unique identifier for the record
        vector: Embedding vector
        payload: Additional metadata/payload
        tenant_id: Tenant identifier for multi-tenancy
        document_id: Source document identifier
        chunk_index: Index of chunk within document
    """

    id: str
    vector: list[float]
    payload: dict[str, Any] = field(default_factory=dict)
    tenant_id: UUID | None = None
    document_id: str | None = None
    chunk_index: int = 0


@dataclass
class SearchResult:
    """Result from vector similarity search.

    Attributes:
        id: Record identifier
        score: Similarity score (higher is more similar)
        payload: Record metadata
        vector: Optional vector (if requested)
    """

    id: str
    score: float
    payload: dict[str, Any] = field(default_factory=dict)
    vector: list[float] | None = None


class VectorStore(ABC):
    """Abstract base class for vector store implementations.

    Provides a unified interface for vector database operations
    supporting multi-tenancy and metadata filtering.

    All implementations must be async-compatible and handle:
    - Collection management
    - Vector CRUD operations
    - Similarity search with filters
    - Batch operations for efficiency
    """

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize connection to vector database.

        Should be called before any other operations.
        May create default collections or verify connectivity.
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close connection to vector database.

        Clean up any resources.
        """
        pass

    @abstractmethod
    async def create_collection(
        self,
        name: str,
        dimension: int,
        *,
        distance_metric: str = "cosine",
        on_disk: bool = False,
    ) -> bool:
        """Create a new vector collection.

        Args:
            name: Collection name
            dimension: Vector dimension
            distance_metric: Distance metric (cosine, euclid, dot)
            on_disk: Whether to store vectors on disk

        Returns:
            True if created, False if already exists
        """
        pass

    @abstractmethod
    async def delete_collection(self, name: str) -> bool:
        """Delete a collection.

        Args:
            name: Collection name

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def collection_exists(self, name: str) -> bool:
        """Check if collection exists.

        Args:
            name: Collection name

        Returns:
            True if collection exists
        """
        pass

    @abstractmethod
    async def upsert(
        self,
        collection: str,
        records: list[VectorRecord],
        *,
        wait: bool = True,
    ) -> int:
        """Insert or update vector records.

        Args:
            collection: Collection name
            records: Records to upsert
            wait: Wait for operation to complete

        Returns:
            Number of records upserted
        """
        pass

    @abstractmethod
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
        """Search for similar vectors.

        Args:
            collection: Collection name
            query_vector: Query embedding vector
            limit: Maximum number of results
            filters: Optional metadata filters
            tenant_id: Filter by tenant ID
            include_vectors: Include vectors in results
            score_threshold: Minimum similarity score

        Returns:
            List of search results sorted by similarity
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    async def delete_by_filter(
        self,
        collection: str,
        filters: list[SearchFilter],
        *,
        tenant_id: UUID | None = None,
    ) -> int:
        """Delete records matching filters.

        Args:
            collection: Collection name
            filters: Filter conditions
            tenant_id: Optional tenant filter

        Returns:
            Number of records deleted
        """
        pass

    @abstractmethod
    async def count(
        self,
        collection: str,
        *,
        filters: list[SearchFilter] | None = None,
        tenant_id: UUID | None = None,
    ) -> int:
        """Count records in collection.

        Args:
            collection: Collection name
            filters: Optional filter conditions
            tenant_id: Optional tenant filter

        Returns:
            Number of matching records
        """
        pass

    @abstractmethod
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
            ids: Record IDs to retrieve
            include_vectors: Include vectors in results

        Returns:
            List of matching records
        """
        pass

    # Utility methods with default implementations

    async def health_check(self) -> bool:
        """Check if vector store is healthy.

        Returns:
            True if healthy and reachable
        """
        try:
            # Default: try to list collections
            await self.collection_exists("_health_check_")
            return True
        except Exception:
            return False
