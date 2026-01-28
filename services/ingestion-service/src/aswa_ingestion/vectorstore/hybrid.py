"""Hybrid search combining vector similarity and BM25 lexical search.

Provides HybridSearcher for combining dense and sparse retrieval
with RRF (Reciprocal Rank Fusion), and ReRanker for cross-encoder
reranking of results.
"""

import asyncio
import math
from dataclasses import dataclass, field
from typing import Any, Callable
from uuid import UUID

from pydantic import BaseModel

from aswa_common.logging import get_logger

from aswa_ingestion.vectorstore.base import (
    VectorStore,
    SearchResult,
    SearchFilter,
)

logger = get_logger(__name__)


@dataclass
class HybridResult:
    """Result from hybrid search with source scores.

    Attributes:
        id: Record identifier
        combined_score: Final fused score
        vector_score: Score from vector search
        bm25_score: Score from BM25 search
        payload: Record metadata
        text: Original text (if available)
    """

    id: str
    combined_score: float
    vector_score: float | None = None
    bm25_score: float | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    text: str | None = None


class HybridSearchMetrics(BaseModel):
    """Metrics for hybrid search operations."""

    total_searches: int = 0
    vector_searches: int = 0
    bm25_searches: int = 0
    avg_vector_latency_ms: float = 0
    avg_bm25_latency_ms: float = 0
    avg_fusion_latency_ms: float = 0


class HybridSearcher:
    """Combines vector similarity search with BM25 lexical search.

    Uses Reciprocal Rank Fusion (RRF) to combine results from
    dense vector retrieval and sparse BM25 retrieval for
    improved retrieval quality.

    Features:
    - Parallel execution of vector and BM25 searches
    - Configurable fusion weights
    - Score normalization
    - Deduplication of results
    """

    def __init__(
        self,
        vector_store: VectorStore,
        bm25_search_fn: Callable[[str, int, UUID | None], list[tuple[str, float]]] | None = None,
        vector_weight: float = 0.7,
        bm25_weight: float = 0.3,
        rrf_k: int = 60,
    ) -> None:
        """Initialize hybrid searcher.

        Args:
            vector_store: Vector store for dense retrieval
            bm25_search_fn: Function for BM25 search, returns list of (id, score) tuples
            vector_weight: Weight for vector search scores (0-1)
            bm25_weight: Weight for BM25 scores (0-1)
            rrf_k: RRF ranking constant (higher = smoother blending)
        """
        self.vector_store = vector_store
        self.bm25_search_fn = bm25_search_fn
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight
        self.rrf_k = rrf_k

        self.metrics = HybridSearchMetrics()

        logger.info(
            f"HybridSearcher initialized: vector_weight={vector_weight}, "
            f"bm25_weight={bm25_weight}, rrf_k={rrf_k}"
        )

    async def search(
        self,
        collection: str,
        query_text: str,
        query_vector: list[float],
        *,
        limit: int = 10,
        filters: list[SearchFilter] | None = None,
        tenant_id: UUID | None = None,
        oversample_factor: int = 3,
    ) -> list[HybridResult]:
        """Perform hybrid search combining vector and BM25 retrieval.

        Args:
            collection: Collection to search
            query_text: Query text for BM25
            query_vector: Query embedding for vector search
            limit: Number of results to return
            filters: Optional metadata filters
            tenant_id: Tenant ID for filtering
            oversample_factor: Factor to oversample before fusion

        Returns:
            Fused and ranked results
        """
        self.metrics.total_searches += 1
        oversample_limit = limit * oversample_factor

        # Run vector and BM25 searches in parallel
        vector_task = self._vector_search(
            collection, query_vector, oversample_limit, filters, tenant_id
        )

        if self.bm25_search_fn:
            bm25_task = self._bm25_search(query_text, oversample_limit, tenant_id)
            vector_results, bm25_results = await asyncio.gather(vector_task, bm25_task)
        else:
            vector_results = await vector_task
            bm25_results = []

        # Fuse results using RRF
        fused_results = self._fuse_rrf(vector_results, bm25_results, limit)

        logger.debug(
            f"Hybrid search: {len(vector_results)} vector, "
            f"{len(bm25_results)} bm25, {len(fused_results)} fused"
        )

        return fused_results

    async def _vector_search(
        self,
        collection: str,
        query_vector: list[float],
        limit: int,
        filters: list[SearchFilter] | None,
        tenant_id: UUID | None,
    ) -> list[SearchResult]:
        """Perform vector similarity search.

        Args:
            collection: Collection name
            query_vector: Query embedding
            limit: Max results
            filters: Metadata filters
            tenant_id: Tenant filter

        Returns:
            Vector search results
        """
        import time

        start = time.time()

        results = await self.vector_store.search(
            collection,
            query_vector,
            limit=limit,
            filters=filters,
            tenant_id=tenant_id,
        )

        elapsed_ms = (time.time() - start) * 1000
        self.metrics.vector_searches += 1
        self.metrics.avg_vector_latency_ms = (
            self.metrics.avg_vector_latency_ms * (self.metrics.vector_searches - 1)
            + elapsed_ms
        ) / self.metrics.vector_searches

        return results

    async def _bm25_search(
        self,
        query_text: str,
        limit: int,
        tenant_id: UUID | None,
    ) -> list[tuple[str, float]]:
        """Perform BM25 lexical search.

        Args:
            query_text: Query text
            limit: Max results
            tenant_id: Tenant filter

        Returns:
            List of (id, score) tuples
        """
        import time

        if not self.bm25_search_fn:
            return []

        start = time.time()

        # BM25 search function might be sync or async
        result = self.bm25_search_fn(query_text, limit, tenant_id)
        if asyncio.iscoroutine(result):
            results = await result
        else:
            results = result

        elapsed_ms = (time.time() - start) * 1000
        self.metrics.bm25_searches += 1
        self.metrics.avg_bm25_latency_ms = (
            self.metrics.avg_bm25_latency_ms * (self.metrics.bm25_searches - 1)
            + elapsed_ms
        ) / self.metrics.bm25_searches

        return results

    def _fuse_rrf(
        self,
        vector_results: list[SearchResult],
        bm25_results: list[tuple[str, float]],
        limit: int,
    ) -> list[HybridResult]:
        """Fuse results using Reciprocal Rank Fusion (RRF).

        RRF score = sum(1 / (k + rank)) for each list

        Args:
            vector_results: Results from vector search
            bm25_results: Results from BM25 search
            limit: Max results to return

        Returns:
            Fused results sorted by combined score
        """
        # Build score maps
        vector_scores: dict[str, float] = {}
        vector_ranks: dict[str, int] = {}
        vector_payloads: dict[str, dict[str, Any]] = {}

        for rank, result in enumerate(vector_results):
            vector_scores[result.id] = result.score
            vector_ranks[result.id] = rank + 1
            vector_payloads[result.id] = result.payload

        bm25_scores: dict[str, float] = {}
        bm25_ranks: dict[str, int] = {}

        for rank, (doc_id, score) in enumerate(bm25_results):
            bm25_scores[doc_id] = score
            bm25_ranks[doc_id] = rank + 1

        # Calculate RRF scores
        all_ids = set(vector_ranks.keys()) | set(bm25_ranks.keys())
        rrf_scores: dict[str, float] = {}

        for doc_id in all_ids:
            score = 0.0

            if doc_id in vector_ranks:
                score += self.vector_weight * (1.0 / (self.rrf_k + vector_ranks[doc_id]))

            if doc_id in bm25_ranks:
                score += self.bm25_weight * (1.0 / (self.rrf_k + bm25_ranks[doc_id]))

            rrf_scores[doc_id] = score

        # Sort by RRF score and build results
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

        results = []
        for doc_id in sorted_ids[:limit]:
            results.append(
                HybridResult(
                    id=doc_id,
                    combined_score=rrf_scores[doc_id],
                    vector_score=vector_scores.get(doc_id),
                    bm25_score=bm25_scores.get(doc_id),
                    payload=vector_payloads.get(doc_id, {}),
                )
            )

        return results

    async def vector_only_search(
        self,
        collection: str,
        query_vector: list[float],
        *,
        limit: int = 10,
        filters: list[SearchFilter] | None = None,
        tenant_id: UUID | None = None,
    ) -> list[HybridResult]:
        """Perform vector-only search (convenience method).

        Args:
            collection: Collection name
            query_vector: Query embedding
            limit: Max results
            filters: Metadata filters
            tenant_id: Tenant filter

        Returns:
            Search results as HybridResult
        """
        results = await self._vector_search(
            collection, query_vector, limit, filters, tenant_id
        )

        return [
            HybridResult(
                id=r.id,
                combined_score=r.score,
                vector_score=r.score,
                payload=r.payload,
            )
            for r in results
        ]


class ReRanker:
    """Cross-encoder reranker for improving search results.

    Uses a cross-encoder model to rerank initial retrieval results
    for better relevance ordering.
    """

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        device: str | None = None,
        batch_size: int = 32,
    ) -> None:
        """Initialize reranker.

        Args:
            model_name: Cross-encoder model name
            device: Device to run on (cuda, cpu, mps)
            batch_size: Batch size for inference
        """
        self.model_name = model_name
        self.device = device
        self.batch_size = batch_size

        self._model: Any = None
        self._initialized = False

        logger.info(f"ReRanker initialized with model: {model_name}")

    async def initialize(self) -> None:
        """Load cross-encoder model."""
        if self._initialized:
            return

        try:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(
                self.model_name,
                max_length=512,
                device=self.device,
            )
            self._initialized = True
            logger.info(f"Loaded cross-encoder model: {self.model_name}")
        except ImportError:
            logger.warning("sentence-transformers not installed, reranking disabled")
            self._initialized = False

    async def rerank(
        self,
        query: str,
        results: list[HybridResult],
        *,
        text_field: str = "text",
        top_k: int | None = None,
    ) -> list[HybridResult]:
        """Rerank results using cross-encoder.

        Args:
            query: Query text
            results: Results to rerank
            text_field: Payload field containing text
            top_k: Limit results after reranking

        Returns:
            Reranked results
        """
        if not self._initialized or self._model is None:
            await self.initialize()

        if not self._initialized or self._model is None or not results:
            return results

        # Extract texts
        pairs = []
        valid_indices = []

        for i, result in enumerate(results):
            text = result.text or result.payload.get(text_field)
            if text:
                pairs.append([query, text])
                valid_indices.append(i)

        if not pairs:
            return results

        # Score with cross-encoder (runs sync, wrap in executor)
        import asyncio

        loop = asyncio.get_event_loop()
        scores = await loop.run_in_executor(
            None,
            lambda: self._model.predict(pairs, batch_size=self.batch_size),
        )

        # Update scores
        reranked = list(results)
        for idx, score in zip(valid_indices, scores):
            reranked[idx] = HybridResult(
                id=reranked[idx].id,
                combined_score=float(score),
                vector_score=reranked[idx].vector_score,
                bm25_score=reranked[idx].bm25_score,
                payload=reranked[idx].payload,
                text=reranked[idx].text,
            )

        # Sort by new scores
        reranked.sort(key=lambda x: x.combined_score, reverse=True)

        if top_k:
            reranked = reranked[:top_k]

        logger.debug(f"Reranked {len(results)} results to {len(reranked)}")
        return reranked


def normalize_scores(
    results: list[HybridResult],
    min_score: float = 0.0,
    max_score: float = 1.0,
) -> list[HybridResult]:
    """Normalize combined scores to a range.

    Args:
        results: Results to normalize
        min_score: Minimum output score
        max_score: Maximum output score

    Returns:
        Results with normalized scores
    """
    if not results:
        return results

    scores = [r.combined_score for r in results]
    current_min = min(scores)
    current_max = max(scores)

    if current_max == current_min:
        # All same score, set to midpoint
        mid = (min_score + max_score) / 2
        return [
            HybridResult(
                id=r.id,
                combined_score=mid,
                vector_score=r.vector_score,
                bm25_score=r.bm25_score,
                payload=r.payload,
                text=r.text,
            )
            for r in results
        ]

    # Min-max normalization
    scale = (max_score - min_score) / (current_max - current_min)

    return [
        HybridResult(
            id=r.id,
            combined_score=min_score + (r.combined_score - current_min) * scale,
            vector_score=r.vector_score,
            bm25_score=r.bm25_score,
            payload=r.payload,
            text=r.text,
        )
        for r in results
    ]
