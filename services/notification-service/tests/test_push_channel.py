import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aswa_notifications.channels.push import (
    PushChannel,
    PushPayloadBuilder,
    DeviceTokenManager,
)


class TestPushChannel:
    @pytest.fixture
    def settings(self):
        settings = MagicMock()
        settings.firebase_credentials_path = ""
        settings.apns_key_path = ""
        settings.apns_key_id = ""
        settings.apns_team_id = ""
        settings.environment = "development"
        return settings

    @pytest.fixture
    def channel(self, settings):
        return PushChannel(settings)

    @pytest.mark.asyncio
    async def test_verify_with_tokens(self, channel):
        """Test verification with tokens."""
        assert await channel.verify_recipient({"tokens": [{"token": "abc123"}]}) is True

    @pytest.mark.asyncio
    async def test_verify_without_tokens(self, channel):
        """Test verification without tokens."""
        assert await channel.verify_recipient({"tokens": []}) is False
        assert await channel.verify_recipient({}) is False

    @pytest.mark.asyncio
    async def test_send_no_tokens(self, channel):
        """Test send fails without tokens."""
        with pytest.raises(ValueError, match="No push tokens"):
            await channel.send(
                recipient={"tokens": []},
                subject="Test",
                content={"body": "Test"},
                priority="normal",
            )


class TestPushPayloadBuilder:
    def test_insight_alert_risk(self):
        """Test risk alert payload."""
        payload = PushPayloadBuilder.insight_alert(
            insight_id="insight-123",
            insight_title="Security Risk",
            insight_type="risk",
            severity="critical",
        )

        assert "Risk" in payload["title"]
        assert "Security Risk" in payload["body"]
        assert payload["data"]["type"] == "insight_alert"
        assert payload["data"]["insight_id"] == "insight-123"
        assert payload["data"]["severity"] == "critical"

    def test_insight_alert_opportunity(self):
        """Test opportunity alert payload."""
        payload = PushPayloadBuilder.insight_alert(
            insight_id="insight-456",
            insight_title="Cost Savings",
            insight_type="opportunity",
            severity="high",
        )

        assert "Opportunity" in payload["title"]
        assert "Info" in payload["title"]

    def test_document_processed(self):
        """Test document processed payload."""
        payload = PushPayloadBuilder.document_processed(
            document_id="doc-123",
            document_name="Report.pdf",
            insight_count=15,
        )

        assert "Processed" in payload["title"]
        assert "Report.pdf" in payload["body"]
        assert "15" in payload["body"]
        assert payload["data"]["action"] == "view_document"

    def test_document_failed(self):
        """Test document failed payload."""
        payload = PushPayloadBuilder.document_failed(
            document_id="doc-456",
            document_name="Bad.pdf",
            error="File corrupted",
        )

        assert "Failed" in payload["title"]
        assert "Bad.pdf" in payload["body"]
        assert payload["data"]["error"] == "File corrupted"

    def test_mention(self):
        """Test mention payload."""
        payload = PushPayloadBuilder.mention(
            from_user="John Doe",
            context="Hey, check this insight about revenue",
            target_id="insight-789",
            target_type="insight",
        )

        assert "John Doe" in payload["title"]
        assert "mentioned" in payload["title"]
        assert "revenue" in payload["body"]


class TestDeviceTokenManager:
    @pytest.fixture
    def session_factory(self):
        return MagicMock()

    @pytest.fixture
    def manager(self, session_factory):
        return DeviceTokenManager(session_factory)

    @pytest.mark.asyncio
    async def test_register_token(self, manager):
        """Test token registration."""
        # Would require database setup for full test
        pass

    @pytest.mark.asyncio
    async def test_unregister_token(self, manager):
        """Test token unregistration."""
        # Would require database setup for full test
        pass
