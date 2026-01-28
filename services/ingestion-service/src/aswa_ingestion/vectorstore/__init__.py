"""Vector store integration for ASWA ingestion service.

This module provides an abstraction layer for vector databases,
with implementations for Qdrant and hybrid search capabilities.
"""

from aswa_ingestion.vectorstore.base import (
    VectorStore,
    VectorRecord,
    SearchResult,
    SearchFilter,
    FilterOperator,
)
from aswa_ingestion.vectorstore.qdrant import QdrantVectorStore
from aswa_ingestion.vectorstore.hybrid import HybridSearcher, ReRanker

__all__ = [
    "VectorStore",
    "VectorRecord",
    "SearchResult",
    "SearchFilter",
    "FilterOperator",
    "QdrantVectorStore",
    "HybridSearcher",
    "ReRanker",
]
