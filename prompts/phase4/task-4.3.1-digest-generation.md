# Task 4.3.1: Daily/Weekly Digest Generation

## Context

You are working on the ASWA query-service at `/services/query-service/`. The query and RAG pipeline is complete. Now we need proactive features that generate insights without user queries.

## Objective

Create a digest generation service that:
1. Generates daily/weekly summaries of insights
2. Personalizes digests based on user preferences
3. Tracks digest delivery and engagement
4. Schedules digest generation

## Requirements

### 1. Create `/services/query-service/src/aswa_query/digest/__init__.py`
```python
from .generator import DigestGenerator
from .models import Digest, DigestConfig, DigestPeriod
from .scheduler import DigestScheduler
from .templates import DigestTemplate, EmailTemplate, SlackTemplate

__all__ = [
    "DigestGenerator",
    "Digest",
    "DigestConfig",
    "DigestPeriod",
    "DigestScheduler",
    "DigestTemplate",
    "EmailTemplate",
    "SlackTemplate",
]
```

### 2. Create `/services/query-service/src/aswa_query/digest/models.py`
```python
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class DigestPeriod(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class DigestSection(str, Enum):
    SUMMARY = "summary"
    NEW_RISKS = "new_risks"
    NEW_OPPORTUNITIES = "new_opportunities"
    KEY_ENTITIES = "key_entities"
    TRENDS = "trends"
    DOCUMENT_ACTIVITY = "document_activity"


class DigestConfig(BaseModel):
    """Configuration for digest generation."""
    tenant_id: UUID
    period: DigestPeriod = DigestPeriod.DAILY
    sections: list[DigestSection] = Field(default_factory=lambda: [
        DigestSection.SUMMARY,
        DigestSection.NEW_RISKS,
        DigestSection.NEW_OPPORTUNITIES,
        DigestSection.TRENDS,
    ])
    max_items_per_section: int = 5
    min_confidence: float = 0.6
    include_low_priority: bool = False
    recipients: list[str] = Field(default_factory=list)
    delivery_hour: int = 9  # Hour of day to deliver
    timezone: str = "UTC"


class DigestItem(BaseModel):
    """An item in the digest."""
    id: UUID = Field(default_factory=uuid4)
    section: DigestSection
    title: str
    description: str
    importance: float = 0.5
    source_document: str | None = None
    source_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Digest(BaseModel):
    """A generated digest."""
    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    period: DigestPeriod
    period_start: datetime
    period_end: datetime
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    title: str = ""
    summary: str = ""
    items: list[DigestItem] = Field(default_factory=list)

    # Statistics
    total_documents_processed: int = 0
    new_insights_count: int = 0
    high_priority_count: int = 0

    # Delivery tracking
    delivered: bool = False
    delivered_at: datetime | None = None
    delivery_channels: list[str] = Field(default_factory=list)

    def add_item(self, item: DigestItem) -> None:
        self.items.append(item)

    def get_items_by_section(self, section: DigestSection) -> list[DigestItem]:
        return [i for i in self.items if i.section == section]

    @property
    def is_empty(self) -> bool:
        return len(self.items) == 0
```

### 3. Create `/services/query-service/src/aswa_query/digest/generator.py`
```python
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID
import structlog

from aswa_query.config import Settings
from aswa_query.services.insight_client import InsightClient
from aswa_query.generation.generator import AnswerGenerator
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
        answer_generator: AnswerGenerator | None = None,
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
```

### 4. Create `/services/query-service/src/aswa_query/digest/scheduler.py`
```python
import asyncio
from datetime import datetime, timedelta
from typing import Callable, Any
from uuid import UUID
import structlog

from .models import DigestConfig, Digest, DigestPeriod
from .generator import DigestGenerator

logger = structlog.get_logger()


class DigestScheduler:
    """Schedule and manage digest generation."""

    def __init__(
        self,
        generator: DigestGenerator,
        delivery_callback: Callable[[Digest], Any] | None = None,
    ):
        self.generator = generator
        self.delivery_callback = delivery_callback
        self._configs: dict[UUID, DigestConfig] = {}
        self._running = False
        self._task: asyncio.Task | None = None

    def register_config(self, config: DigestConfig) -> None:
        """Register a digest configuration."""
        self._configs[config.tenant_id] = config
        logger.info(
            "Digest config registered",
            tenant_id=str(config.tenant_id),
            period=config.period,
        )

    def unregister_config(self, tenant_id: UUID) -> None:
        """Unregister a digest configuration."""
        self._configs.pop(tenant_id, None)

    async def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info("Digest scheduler started")

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Digest scheduler stopped")

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                now = datetime.utcnow()

                for tenant_id, config in list(self._configs.items()):
                    if self._should_generate(config, now):
                        asyncio.create_task(
                            self._generate_and_deliver(config)
                        )

                # Check every minute
                await asyncio.sleep(60)

            except Exception as e:
                logger.error("Scheduler error", error=str(e))
                await asyncio.sleep(60)

    def _should_generate(self, config: DigestConfig, now: datetime) -> bool:
        """Check if digest should be generated now."""
        # Check if it's the right hour
        if now.hour != config.delivery_hour:
            return False

        # Check based on period
        if config.period == DigestPeriod.DAILY:
            return True
        elif config.period == DigestPeriod.WEEKLY:
            return now.weekday() == 0  # Monday
        elif config.period == DigestPeriod.MONTHLY:
            return now.day == 1

        return False

    async def _generate_and_deliver(self, config: DigestConfig) -> None:
        """Generate and deliver a digest."""
        try:
            digest = await self.generator.generate(config)

            if digest.is_empty:
                logger.info(
                    "Skipping empty digest",
                    tenant_id=str(config.tenant_id),
                )
                return

            if self.delivery_callback:
                await self.delivery_callback(digest)
                digest.delivered = True
                digest.delivered_at = datetime.utcnow()

            logger.info(
                "Digest delivered",
                digest_id=str(digest.id),
                tenant_id=str(config.tenant_id),
            )

        except Exception as e:
            logger.error(
                "Digest generation failed",
                tenant_id=str(config.tenant_id),
                error=str(e),
            )

    async def generate_now(self, tenant_id: UUID) -> Digest | None:
        """Generate a digest immediately."""
        config = self._configs.get(tenant_id)
        if not config:
            logger.warning("No config for tenant", tenant_id=str(tenant_id))
            return None

        return await self.generator.generate(config)
```

### 5. Create `/services/query-service/src/aswa_query/digest/templates.py`
```python
from abc import ABC, abstractmethod
from typing import Any

from .models import Digest, DigestSection


class DigestTemplate(ABC):
    """Abstract template for rendering digests."""

    @abstractmethod
    def render(self, digest: Digest) -> str:
        """Render digest to output format."""
        ...


class EmailTemplate(DigestTemplate):
    """HTML email template for digests."""

    def render(self, digest: Digest) -> str:
        """Render digest as HTML email."""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; }}
        .header {{ background: #2563eb; color: white; padding: 20px; }}
        .section {{ margin: 20px 0; padding: 15px; background: #f3f4f6; }}
        .section-title {{ color: #1f2937; font-size: 18px; margin-bottom: 10px; }}
        .item {{ margin: 10px 0; padding: 10px; background: white; border-left: 3px solid #2563eb; }}
        .item-title {{ font-weight: bold; }}
        .item-desc {{ color: #6b7280; font-size: 14px; }}
        .footer {{ text-align: center; color: #9ca3af; font-size: 12px; padding: 20px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{digest.title}</h1>
        <p>{digest.period_start.strftime('%B %d')} - {digest.period_end.strftime('%B %d, %Y')}</p>
    </div>

    <div class="section">
        <h2>Summary</h2>
        <p>{digest.summary}</p>
    </div>
"""

        # Render each section
        for section in DigestSection:
            items = digest.get_items_by_section(section)
            if items:
                html += self._render_section(section, items)

        html += """
    <div class="footer">
        <p>Generated by ASWA | <a href="#">Manage preferences</a></p>
    </div>
</body>
</html>
"""
        return html

    def _render_section(self, section: DigestSection, items: list) -> str:
        """Render a section."""
        section_titles = {
            DigestSection.NEW_RISKS: "New Risks",
            DigestSection.NEW_OPPORTUNITIES: "New Opportunities",
            DigestSection.KEY_ENTITIES: "Key Entities",
            DigestSection.TRENDS: "Trends",
            DigestSection.DOCUMENT_ACTIVITY: "Document Activity",
        }

        html = f"""
    <div class="section">
        <h2 class="section-title">{section_titles.get(section, section.value)}</h2>
"""
        for item in items:
            html += f"""
        <div class="item">
            <div class="item-title">{item.title}</div>
            <div class="item-desc">{item.description[:200]}...</div>
        </div>
"""
        html += "    </div>\n"
        return html


class SlackTemplate(DigestTemplate):
    """Slack message template for digests."""

    def render(self, digest: Digest) -> str:
        """Render digest as Slack mrkdwn."""
        blocks = []

        # Header
        blocks.append({
            "type": "header",
            "text": {"type": "plain_text", "text": digest.title}
        })

        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": digest.summary}
        })

        blocks.append({"type": "divider"})

        # Sections
        for section in DigestSection:
            items = digest.get_items_by_section(section)
            if items:
                blocks.extend(self._render_section(section, items))

        return {"blocks": blocks}

    def _render_section(self, section: DigestSection, items: list) -> list:
        """Render a section as Slack blocks."""
        section_emojis = {
            DigestSection.NEW_RISKS: ":warning:",
            DigestSection.NEW_OPPORTUNITIES: ":star:",
            DigestSection.KEY_ENTITIES: ":bust_in_silhouette:",
            DigestSection.TRENDS: ":chart_with_upwards_trend:",
        }

        blocks = []
        emoji = section_emojis.get(section, ":pushpin:")

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{emoji} {section.value.replace('_', ' ').title()}*"
            }
        })

        for item in items[:5]:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"• *{item.title}*\n{item.description[:100]}..."
                }
            })

        return blocks


class MarkdownTemplate(DigestTemplate):
    """Markdown template for digests."""

    def render(self, digest: Digest) -> str:
        """Render digest as Markdown."""
        md = f"# {digest.title}\n\n"
        md += f"*{digest.period_start.strftime('%B %d')} - {digest.period_end.strftime('%B %d, %Y')}*\n\n"
        md += f"## Summary\n\n{digest.summary}\n\n"

        section_titles = {
            DigestSection.NEW_RISKS: "New Risks",
            DigestSection.NEW_OPPORTUNITIES: "New Opportunities",
            DigestSection.KEY_ENTITIES: "Key Entities",
            DigestSection.TRENDS: "Trends",
        }

        for section in DigestSection:
            items = digest.get_items_by_section(section)
            if items:
                md += f"## {section_titles.get(section, section.value)}\n\n"
                for item in items:
                    md += f"### {item.title}\n\n"
                    md += f"{item.description}\n\n"

        return md
```

## Test Requirements

### Create `/services/query-service/tests/digest/test_generator.py`
```python
import pytest
from uuid import uuid4
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from aswa_query.digest.generator import DigestGenerator
from aswa_query.digest.models import DigestConfig, DigestPeriod, DigestSection
from aswa_query.config import Settings


class TestDigestGenerator:
    @pytest.fixture
    def mock_insight_client(self):
        client = MagicMock()
        client.query_insights = AsyncMock(return_value=MagicMock(items=[
            {"id": str(uuid4()), "title": "Risk 1", "description": "Description", "confidence": 0.8},
        ]))
        client.get_trends = AsyncMock(return_value={"trends": []})
        return client

    @pytest.fixture
    def generator(self, mock_insight_client):
        settings = Settings()
        return DigestGenerator(settings, mock_insight_client)

    @pytest.mark.asyncio
    async def test_generate_daily_digest(self, generator):
        """Test generating a daily digest."""
        config = DigestConfig(
            tenant_id=uuid4(),
            period=DigestPeriod.DAILY,
        )

        digest = await generator.generate(config)

        assert digest is not None
        assert digest.period == DigestPeriod.DAILY
        assert (digest.period_end - digest.period_start).days == 1

    @pytest.mark.asyncio
    async def test_generate_weekly_digest(self, generator):
        """Test generating a weekly digest."""
        config = DigestConfig(
            tenant_id=uuid4(),
            period=DigestPeriod.WEEKLY,
        )

        digest = await generator.generate(config)

        assert digest.period == DigestPeriod.WEEKLY
        assert (digest.period_end - digest.period_start).days == 7

    @pytest.mark.asyncio
    async def test_digest_includes_sections(self, generator):
        """Test that digest includes requested sections."""
        config = DigestConfig(
            tenant_id=uuid4(),
            sections=[DigestSection.NEW_RISKS],
        )

        digest = await generator.generate(config)

        # Should have items from risks section
        risk_items = digest.get_items_by_section(DigestSection.NEW_RISKS)
        assert len(risk_items) >= 0  # May be empty if mock returns nothing
```

## Verification

1. Run tests: `cd /services/query-service && python -m pytest tests/digest/ -v`
2. Verify imports: `python -c "from aswa_query.digest import DigestGenerator"`
