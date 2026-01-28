from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID
import hashlib
import structlog

from sqlalchemy.ext.asyncio import AsyncSession

from .insight_repo import InsightRepository
from .models import InsightModel
from aswa_insight.models.insights import Insight, InsightType
from aswa_insight.scoring.confidence import ConfidenceAggregator

logger = structlog.get_logger()


@dataclass
class DuplicateMatch:
    """A potential duplicate match."""
    existing_insight: InsightModel
    similarity_score: float
    match_reason: str


class DuplicateDetector:
    """Detect duplicate insights."""

    def __init__(
        self,
        similarity_threshold: float = 0.85,
    ):
        self.similarity_threshold = similarity_threshold

    def compute_hash(self, insight: Insight) -> str:
        """Compute content hash for exact matching."""
        content = (
            f"{insight.tenant_id}:"
            f"{insight.insight_type.value}:"
            f"{self._normalize(insight.title)}"
        )
        return hashlib.sha256(content.encode()).hexdigest()

    def compute_similarity(
        self,
        insight1: Insight | InsightModel,
        insight2: Insight | InsightModel,
    ) -> float:
        """Compute similarity between two insights."""
        # Title similarity (Jaccard)
        title1 = self._normalize(self._get_title(insight1))
        title2 = self._normalize(self._get_title(insight2))

        words1 = set(title1.split())
        words2 = set(title2.split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)
        title_sim = intersection / union if union > 0 else 0.0

        # Type must match
        type1 = self._get_type(insight1)
        type2 = self._get_type(insight2)
        if type1 != type2:
            return 0.0

        # Category similarity (bonus if same)
        cat1 = self._get_category(insight1)
        cat2 = self._get_category(insight2)
        category_bonus = 0.1 if cat1 and cat1 == cat2 else 0.0

        return min(1.0, title_sim + category_bonus)

    def _normalize(self, text: str) -> str:
        return text.lower().strip()

    def _get_title(self, insight: Insight | InsightModel) -> str:
        if isinstance(insight, InsightModel):
            return insight.title
        return insight.title

    def _get_type(self, insight: Insight | InsightModel) -> str:
        if isinstance(insight, InsightModel):
            return insight.insight_type
        return insight.insight_type.value

    def _get_category(self, insight: Insight | InsightModel) -> str | None:
        return insight.category


class DeduplicationService:
    """Service for deduplicating insights."""

    def __init__(
        self,
        session: AsyncSession,
        detector: DuplicateDetector | None = None,
    ):
        self.session = session
        self.repository = InsightRepository(session)
        self.detector = detector or DuplicateDetector()
        self.confidence_aggregator = ConfidenceAggregator()

    async def check_and_store(
        self,
        insight: Insight,
        merge_duplicates: bool = True,
    ) -> tuple[InsightModel, bool]:
        """Check for duplicates and store insight.

        Args:
            insight: Insight to check and store
            merge_duplicates: If True, merge with existing duplicate

        Returns:
            Tuple of (InsightModel, is_new)
        """
        # Check for exact hash match
        content_hash = self.detector.compute_hash(insight)
        existing = await self.repository.find_by_hash(
            insight.tenant_id,
            content_hash,
        )

        if existing:
            logger.info(
                "Exact duplicate found",
                new_insight=str(insight.id),
                existing_insight=str(existing.id),
            )

            if merge_duplicates:
                await self._merge_insights(existing, insight)
            return existing, False

        # Check for similar insights
        similar = await self.repository.find_similar(
            insight.tenant_id,
            insight.title,
            insight.insight_type,
        )

        for existing_similar in similar:
            similarity = self.detector.compute_similarity(insight, existing_similar)
            if similarity >= self.detector.similarity_threshold:
                logger.info(
                    "Similar duplicate found",
                    new_insight=str(insight.id),
                    existing_insight=str(existing_similar.id),
                    similarity=similarity,
                )

                if merge_duplicates:
                    await self._merge_insights(existing_similar, insight)
                return existing_similar, False

        # No duplicate, create new
        new_model = await self.repository.create(insight)
        return new_model, True

    async def deduplicate_batch(
        self,
        insights: list[Insight],
    ) -> tuple[list[InsightModel], dict[str, int]]:
        """Deduplicate a batch of insights.

        Args:
            insights: List of insights to process

        Returns:
            Tuple of (stored_models, stats)
        """
        stored = []
        stats = {
            "total": len(insights),
            "new": 0,
            "merged": 0,
            "exact_duplicates": 0,
            "similar_duplicates": 0,
        }

        for insight in insights:
            model, is_new = await self.check_and_store(insight)
            stored.append(model)

            if is_new:
                stats["new"] += 1
            else:
                stats["merged"] += 1

        logger.info(
            "Batch deduplication complete",
            total=stats["total"],
            new=stats["new"],
            merged=stats["merged"],
        )

        return stored, stats

    async def _merge_insights(
        self,
        existing: InsightModel,
        new: Insight,
    ) -> None:
        """Merge new insight data into existing."""
        # Update confidence (take maximum or aggregate)
        new_confidence = self.confidence_aggregator.max_confidence([
            existing.confidence,
            new.confidence,
        ])
        existing.confidence = new_confidence

        # Merge sources
        existing_sources = existing.sources or []
        new_sources = [s.model_dump() for s in new.sources] if new.sources else []
        merged_sources = existing_sources + [
            s for s in new_sources if s not in existing_sources
        ]
        existing.sources = merged_sources

        # Increment merge count
        existing.merge_count += 1
        existing.updated_at = datetime.utcnow()

        await self.session.flush()

    async def find_duplicates(
        self,
        tenant_id: UUID,
        insight_type: InsightType | None = None,
    ) -> list[list[InsightModel]]:
        """Find duplicate groups in existing insights.

        Returns groups of insights that appear to be duplicates.
        """
        insights, _ = await self.repository.list_insights(
            tenant_id=tenant_id,
            insight_type=insight_type,
            limit=1000,
        )

        # Group by normalized title
        groups: dict[str, list[InsightModel]] = {}

        for insight in insights:
            key = insight.title_normalized
            if key not in groups:
                groups[key] = []
            groups[key].append(insight)

        # Return groups with more than one insight
        return [group for group in groups.values() if len(group) > 1]
