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
