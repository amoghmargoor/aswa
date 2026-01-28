from dataclasses import dataclass, field
from typing import Any
import structlog

from .models import SearchResult, InsightResult

logger = structlog.get_logger()


@dataclass
class RerankerConfig:
    """Configuration for reranking."""
    chunk_weight: float = 0.6
    insight_weight: float = 0.4
    recency_boost: float = 0.1
    confidence_weight: float = 0.2
    keyword_boost: float = 0.15
    diversity_penalty: float = 0.1


class Reranker:
    """Rerank and combine search results."""

    def __init__(self, config: RerankerConfig | None = None):
        self.config = config or RerankerConfig()

    def rerank_chunks(
        self,
        results: list[SearchResult],
        query_keywords: list[str],
        max_results: int = 10,
    ) -> list[SearchResult]:
        """Rerank document chunks.

        Args:
            results: Search results to rerank
            query_keywords: Keywords from parsed query
            max_results: Maximum results to return

        Returns:
            Reranked results
        """
        if not results:
            return []

        scored_results = []
        seen_content_hashes = set()

        for result in results:
            # Calculate combined score
            score = result.score

            # Keyword boost
            content_lower = result.content.lower()
            keyword_matches = sum(1 for kw in query_keywords if kw.lower() in content_lower)
            if query_keywords:
                score += self.config.keyword_boost * (keyword_matches / len(query_keywords))

            # Diversity penalty (penalize similar content)
            content_hash = hash(result.content[:100])
            if content_hash in seen_content_hashes:
                score *= (1 - self.config.diversity_penalty)
            else:
                seen_content_hashes.add(content_hash)

            scored_results.append((score, result))

        # Sort by score descending
        scored_results.sort(key=lambda x: x[0], reverse=True)

        # Return top results with updated scores
        reranked = []
        for score, result in scored_results[:max_results]:
            result.score = score
            reranked.append(result)

        return reranked

    def rerank_insights(
        self,
        insights: list[InsightResult],
        query_keywords: list[str],
        max_results: int = 10,
    ) -> list[InsightResult]:
        """Rerank insights.

        Args:
            insights: Insights to rerank
            query_keywords: Keywords from parsed query
            max_results: Maximum results to return

        Returns:
            Reranked insights
        """
        if not insights:
            return []

        scored_insights = []

        for insight in insights:
            # Base score
            score = insight.score

            # Confidence weight
            score += self.config.confidence_weight * insight.confidence

            # Keyword boost
            text = f"{insight.title} {insight.description}".lower()
            keyword_matches = sum(1 for kw in query_keywords if kw.lower() in text)
            if query_keywords:
                score += self.config.keyword_boost * (keyword_matches / len(query_keywords))

            scored_insights.append((score, insight))

        # Sort by score
        scored_insights.sort(key=lambda x: x[0], reverse=True)

        reranked = []
        for score, insight in scored_insights[:max_results]:
            insight.score = score
            reranked.append(insight)

        return reranked

    def combine_results(
        self,
        chunks: list[SearchResult],
        insights: list[InsightResult],
        max_total: int = 15,
    ) -> tuple[list[SearchResult], list[InsightResult]]:
        """Combine and balance chunk and insight results.

        Args:
            chunks: Document chunks
            insights: Insights
            max_total: Maximum total results

        Returns:
            Tuple of (chunks, insights) with balanced counts
        """
        # Calculate target counts based on weights
        chunk_target = int(max_total * self.config.chunk_weight)
        insight_target = max_total - chunk_target

        # Adjust if one category has fewer results
        if len(chunks) < chunk_target:
            insight_target = min(len(insights), max_total - len(chunks))
            chunk_target = len(chunks)
        elif len(insights) < insight_target:
            chunk_target = min(len(chunks), max_total - len(insights))
            insight_target = len(insights)

        return chunks[:chunk_target], insights[:insight_target]

    def deduplicate_results(
        self,
        results: list[SearchResult],
        similarity_threshold: float = 0.9,
    ) -> list[SearchResult]:
        """Remove near-duplicate results.

        Args:
            results: Results to deduplicate
            similarity_threshold: Jaccard similarity threshold

        Returns:
            Deduplicated results
        """
        if len(results) <= 1:
            return results

        unique_results = []
        seen_contents = []

        for result in results:
            content_words = set(result.content.lower().split())
            is_duplicate = False

            for seen_words in seen_contents:
                if not content_words or not seen_words:
                    continue

                intersection = len(content_words & seen_words)
                union = len(content_words | seen_words)
                similarity = intersection / union if union > 0 else 0

                if similarity >= similarity_threshold:
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique_results.append(result)
                seen_contents.append(content_words)

        return unique_results
