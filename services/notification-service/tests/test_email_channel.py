import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aswa_notifications.channels.email import EmailChannel, EmailTemplateBuilder


class TestEmailChannel:
    @pytest.fixture
    def settings(self):
        settings = MagicMock()
        settings.smtp_host = "localhost"
        settings.smtp_port = 587
        settings.smtp_user = ""
        settings.smtp_password = ""
        settings.smtp_use_tls = False
        settings.email_from = "test@aswa.io"
        settings.email_from_name = "ASWA Test"
        return settings

    @pytest.fixture
    def channel(self, settings):
        return EmailChannel(settings)

    @pytest.mark.asyncio
    async def test_verify_valid_email(self, channel):
        """Test valid email verification."""
        assert await channel.verify_recipient({"email": "test@example.com"}) is True
        assert await channel.verify_recipient({"email": "user.name@domain.co.uk"}) is True

    @pytest.mark.asyncio
    async def test_verify_invalid_email(self, channel):
        """Test invalid email verification."""
        assert await channel.verify_recipient({"email": ""}) is False
        assert await channel.verify_recipient({"email": "not-an-email"}) is False
        assert await channel.verify_recipient({"email": "@nodomain"}) is False
        assert await channel.verify_recipient({}) is False

    def test_build_message(self, channel):
        """Test message building."""
        msg = channel._build_message(
            to_email="test@example.com",
            subject="Test Subject",
            body="Test body content",
            html="<p>Test HTML content</p>",
            priority="high",
        )

        assert msg["To"] == "test@example.com"
        assert msg["Subject"] == "Test Subject"
        assert msg["X-Priority"] == "2"

    def test_build_message_with_urgent_priority(self, channel):
        """Test message building with urgent priority."""
        msg = channel._build_message(
            to_email="test@example.com",
            subject="Urgent Test",
            body="Urgent content",
            priority="urgent",
        )

        assert msg["X-Priority"] == "1"
        assert msg["Importance"] == "High"

    def test_build_message_with_low_priority(self, channel):
        """Test message building with low priority."""
        msg = channel._build_message(
            to_email="test@example.com",
            subject="Low Priority Test",
            body="Low priority content",
            priority="low",
        )

        assert msg["X-Priority"] == "5"
        assert msg["Importance"] == "Low"

    @pytest.mark.asyncio
    async def test_send_missing_email(self, channel):
        """Test send fails without email."""
        with pytest.raises(ValueError, match="email address required"):
            await channel.send(
                recipient={},
                subject="Test",
                content={"body": "Test"},
                priority="normal",
            )


class TestEmailTemplateBuilder:
    def test_insight_alert_risk(self):
        """Test risk alert template."""
        html = EmailTemplateBuilder.insight_alert(
            insight_title="Security Risk",
            insight_type="risk",
            severity="critical",
            confidence=0.95,
            description="A critical security risk was identified.",
            document_name="Security Report.pdf",
            view_url="https://app.aswa.io/insights/123",
        )

        assert "Security Risk" in html
        assert "risk" in html.lower()
        assert "critical" in html.lower()
        assert "95%" in html
        assert "Security Report.pdf" in html

    def test_insight_alert_opportunity(self):
        """Test opportunity alert template."""
        html = EmailTemplateBuilder.insight_alert(
            insight_title="Cost Savings",
            insight_type="opportunity",
            severity="high",
            confidence=0.85,
            description="A cost saving opportunity was identified.",
        )

        assert "Cost Savings" in html
        assert "opportunity" in html.lower()
        assert "alert-success" in html

    def test_digest_template(self):
        """Test digest template."""
        html = EmailTemplateBuilder.digest(
            period="daily",
            date_range="January 15, 2024",
            summary="A productive day with several insights.",
            new_insights=10,
            new_risks=3,
            new_opportunities=5,
            documents_processed=8,
            top_items=[
                {"title": "Risk 1", "type": "risk", "severity": "high"},
                {"title": "Opportunity 1", "type": "opportunity", "severity": "medium"},
            ],
        )

        assert "Daily Digest" in html
        assert "January 15, 2024" in html
        assert "10" in html  # new_insights
        assert "Risk 1" in html

    def test_document_processed_template(self):
        """Test document processed template."""
        html = EmailTemplateBuilder.document_processed(
            document_name="Report.pdf",
            insight_count=15,
            processing_time="2m 30s",
            risk_count=5,
            opportunity_count=8,
        )

        assert "Report.pdf" in html
        assert "15" in html
        assert "2m 30s" in html
        assert "successfully" in html.lower()

    def test_document_failed_template(self):
        """Test document failed template."""
        html = EmailTemplateBuilder.document_failed(
            document_name="Corrupted.pdf",
            error_message="File appears to be corrupted",
        )

        assert "Corrupted.pdf" in html
        assert "corrupted" in html.lower()
        assert "alert-danger" in html

    def test_base_template_includes_footer(self):
        """Test that base template includes footer."""
        html = EmailTemplateBuilder.build(
            title="Test",
            content="<p>Test content</p>",
        )

        assert "ASWA" in html
        assert "Unsubscribe" in html
        assert "Notification Preferences" in html
