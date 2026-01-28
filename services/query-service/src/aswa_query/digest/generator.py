from datetime import datetime, timedelta
from typing import Any
from uuid import UUID
import structlog

from aswa_query.config import Settings
from aswa_query.services.insight_client import InsightClient
from .models import (
    Digest,
    DigestConfig,
    DigestItem,
    DigestPeriod,
    DigestSection,
)

logger = structlog.get_logger()


class DigestGenerator:
    """Generate periodic digests of insights."""

    def __init__(
        self,
        settings: Settings,
        insight_client: InsightClient,
        answer_generator: Any | None = None,
    ):
        self.settings = settings
        self.insight_client = insight_client
        self.answer_generator = answer_generator

    async def generate(
        self,
        config: DigestConfig,
        period_end: datetime | None = None,
    ) -> Digest:
        """Generate a digest.

        Args:
            config: Digest configuration
            period_end: End of period (default: now)

        Returns:
            Generated Digest
        """
        period_end = period_end or datetime.utcnow()
        period_start = self._calculate_period_start(config.period, period_end)

        logger.info(
            "Generating digest",
            tenant_id=str(config.tenant_id),
            period=config.period,
            start=period_start.isoformat(),
            end=period_end.isoformat(),
        )

        digest = Digest(
            tenant_id=config.tenant_id,
            period=config.period,
            period_start=period_start,
            period_end=period_end,
        )

        # Generate each section
        for section in config.sections:
            items = await self._generate_section(
                config=config,
                section=section,
                period_start=period_start,
                period_end=period_end,
            )
            for item in items[:config.max_items_per_section]:
                digest.add_item(item)

        # Generate summary
        if DigestSection.SUMMARY in config.sections:
            digest.summary = await self._generate_summary(digest, config)
            digest.title = self._generate_title(digest, config)

        # Calculate statistics
        digest.new_insights_count = len(digest.items)
        digest.high_priority_count = len([i for i in digest.items if i.importance > 0.7])

        logger.info(
            "Digest generated",
            digest_id=str(digest.id),
            items=len(digest.items),
        )

        return digest

    async def _generate_section(
        self,
        config: DigestConfig,
        section: DigestSection,
        period_start: datetime,
        period_end: datetime,
    ) -> list[DigestItem]:
        """Generate items for a section."""
        if section == DigestSection.NEW_RISKS:
            return await self._get_new_risks(config, period_start, period_end)
        elif section == DigestSection.NEW_OPPORTUNITIES:
            return await self._get_new_opportunities(config, period_start, period_end)
        elif section == DigestSection.KEY_ENTITIES:
            return await self._get_key_entities(config, period_start, period_end)
        elif section == DigestSection.TRENDS:
            return await self._get_trends(config, period_start, period_end)
        elif section == DigestSection.DOCUMENT_ACTIVITY:
            return await self._get_document_activity(config, period_start, period_end)
        return []

    async def _get_new_risks(
        self,
        config: DigestConfig,
        start: datetime,
        end: datetime,
    ) -> list[DigestItem]:
        """Get new risks for the period."""
        try:
            result = await self.insight_client.query_insights(
                tenant_id=config.tenant_id,
                insight_types=["risk"],
                min_confidence=config.min_confidence,
                limit=config.max_items_per_section * 2,
            )

            items = []
            for insight in result.items:
                items.append(DigestItem(
                    section=DigestSection.NEW_RISKS,
                    title=insight.get("title", ""),
                    description=insight.get("description", ""),
                    importance=insight.get("confidence", 0.5),
                    source_id=UUID(insight["id"]) if insight.get("id") else None,
                    metadata={"severity": insight.get("severity")},
                ))

            # Sort by importance
            items.sort(key=lambda i: i.importance, reverse=True)
            return items

        except Exception as e:
            logger.error("Failed to get risks", error=str(e))
            return []

    async def _get_new_opportunities(
        self,
        config: DigestConfig,
        start: datetime,
        end: datetime,
    ) -> list[DigestItem]:
        """Get new opportunities for the period."""
        try:
            result = await self.insight_client.query_insights(
                tenant_id=config.tenant_id,
                insight_types=["opportunity"],
                min_confidence=config.min_confidence,
                limit=config.max_items_per_section * 2,
            )

            items = []
            for insight in result.items:
                items.append(DigestItem(
                    section=DigestSection.NEW_OPPORTUNITIES,
                    title=insight.get("title", ""),
                    description=insight.get("description", ""),
                    importance=insight.get("confidence", 0.5),
                    source_id=UUID(insight["id"]) if insight.get("id") else None,
                    metadata={"impact": insight.get("impact")},
                ))

            items.sort(key=lambda i: i.importance, reverse=True)
            return items

        except Exception as e:
            logger.error("Failed to get opportunities", error=str(e))
            return []

    async def _get_key_entities(
        self,
        config: DigestConfig,
        start: datetime,
        end: datetime,
    ) -> list[DigestItem]:
        """Get key entities mentioned in the period."""
        try:
            result = await self.insight_client.query_insights(
                tenant_id=config.tenant_id,
                insight_types=["entity"],
                min_confidence=config.min_confidence,
                limit=config.max_items_per_section,
            )

            items = []
            for insight in result.items:
                items.append(DigestItem(
                    section=DigestSection.KEY_ENTITIES,
                    title=insight.get("title", ""),
                    description=insight.get("description", ""),
                    importance=insight.get("confidence", 0.5),
                    metadata={"entity_type": insight.get("category")},
                ))

            return items

        except Exception as e:
            logger.error("Failed to get entities", error=str(e))
            return []

    async def _get_trends(
        self,
        config: DigestConfig,
        start: datetime,
        end: datetime,
    ) -> list[DigestItem]:
        """Get identified trends."""
        try:
            trends = await self.insight_client.get_trends(
                config.tenant_id,
                days=(end - start).days,
            )

            items = []
            for trend in trends.get("trends", [])[:config.max_items_per_section]:
                items.append(DigestItem(
                    section=DigestSection.TRENDS,
                    title=trend.get("name", ""),
                    description=trend.get("description", ""),
                    importance=trend.get("strength", 0.5),
                    metadata={"direction": trend.get("direction")},
                ))

            return items

        except Exception as e:
            logger.error("Failed to get trends", error=str(e))
            return []

    async def _get_document_activity(
        self,
        config: DigestConfig,
        start: datetime,
        end: datetime,
    ) -> list[DigestItem]:
        """Get document processing activity."""
        # Would query document service for recent activity
        return []

    async def _generate_summary(
        self,
        digest: Digest,
        config: DigestConfig,
    ) -> str:
        """Generate executive summary of the digest."""
        if not self.answer_generator:
            return self._generate_basic_summary(digest)

        # Use LLM to generate summary
        context_parts = []

        for section in config.sections:
            items = digest.get_items_by_section(section)
            if items:
                section_text = f"\n{section.value.upper()}:\n"
                for item in items[:3]:
                    section_text += f"- {item.title}: {item.description[:100]}...\n"
                context_parts.append(section_text)

        if not context_parts:
            return "No significant insights to report for this period."

        # Generate with LLM (simplified)
        return self._generate_basic_summary(digest)

    def _generate_basic_summary(self, digest: Digest) -> str:
        """Generate basic summary without LLM."""
        parts = []

        risk_count = len(digest.get_items_by_section(DigestSection.NEW_RISKS))
        opp_count = len(digest.get_items_by_section(DigestSection.NEW_OPPORTUNITIES))

        if risk_count:
            parts.append(f"{risk_count} new risks identified")
        if opp_count:
            parts.append(f"{opp_count} new opportunities found")

        if not parts:
            return "No significant changes to report."

        return f"This {digest.period.value} digest includes: " + ", ".join(parts) + "."

    def _generate_title(self, digest: Digest, config: DigestConfig) -> str:
        """Generate digest title."""
        period_name = digest.period.value.capitalize()
        date_str = digest.period_end.strftime("%B %d, %Y")
        return f"{period_name} Insights Digest - {date_str}"

    def _calculate_period_start(
        self,
        period: DigestPeriod,
        end: datetime,
    ) -> datetime:
        """Calculate period start based on period type."""
        if period == DigestPeriod.DAILY:
            return end - timedelta(days=1)
        elif period == DigestPeriod.WEEKLY:
            return end - timedelta(weeks=1)
        elif period == DigestPeriod.MONTHLY:
            return end - timedelta(days=30)
        return end - timedelta(days=1)
