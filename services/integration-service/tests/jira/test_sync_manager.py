import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from aswa_integrations.jira.sync_manager import (
    JiraSyncManager,
    SyncConfig,
    SyncDirection,
    SyncStatus,
)


class TestJiraSyncManager:
    @pytest.fixture
    def sync_config(self):
        return SyncConfig(
            sync_interval_seconds=300,
            sync_status_changes=True,
            sync_comments=True,
            conflict_resolution="jira_wins",
        )

    def test_map_jira_status_to_aswa(self):
        """Test Jira to ASWA status mapping."""
        manager = JiraSyncManager(
            MagicMock(), MagicMock(), MagicMock(), "http://localhost"
        )

        assert manager._map_jira_status_to_aswa("To Do") == "new"
        assert manager._map_jira_status_to_aswa("In Progress") == "in_progress"
        assert manager._map_jira_status_to_aswa("Done") == "resolved"
        assert manager._map_jira_status_to_aswa("Won't Do") == "dismissed"

    def test_map_aswa_status_to_jira(self):
        """Test ASWA to Jira status mapping."""
        manager = JiraSyncManager(
            MagicMock(), MagicMock(), MagicMock(), "http://localhost"
        )

        assert manager._map_aswa_status_to_jira("new") == "To Do"
        assert manager._map_aswa_status_to_jira("in_progress") == "In Progress"
        assert manager._map_aswa_status_to_jira("resolved") == "Done"

    def test_detect_no_changes(self, sync_config):
        """Test detecting no changes."""
        manager = JiraSyncManager(
            MagicMock(), MagicMock(), MagicMock(), "http://localhost"
        )

        jira_issue = MagicMock()
        jira_issue.status = "In Progress"
        jira_issue.priority = "High"

        insight = {"status": "in_progress", "severity": "high"}

        last_sync = {
            "jira_status": "In Progress",
            "jira_priority": "High",
            "aswa_status": "in_progress",
            "aswa_severity": "high",
        }

        changes = manager._detect_changes(
            jira_issue, insight, last_sync, sync_config
        )

        assert not changes["jira_changes"]
        assert not changes["aswa_changes"]

    def test_detect_jira_changes(self, sync_config):
        """Test detecting Jira changes."""
        manager = JiraSyncManager(
            MagicMock(), MagicMock(), MagicMock(), "http://localhost"
        )

        jira_issue = MagicMock()
        jira_issue.status = "Done"  # Changed
        jira_issue.priority = "High"

        insight = {"status": "in_progress", "severity": "high"}

        last_sync = {
            "jira_status": "In Progress",
            "jira_priority": "High",
            "aswa_status": "in_progress",
            "aswa_severity": "high",
        }

        changes = manager._detect_changes(
            jira_issue, insight, last_sync, sync_config
        )

        assert "status" in changes["jira_changes"]
        assert changes["jira_changes"]["status"] == "Done"
        assert not changes["aswa_changes"]

    def test_map_severity_to_priority(self):
        """Test severity to priority mapping."""
        manager = JiraSyncManager(
            MagicMock(), MagicMock(), MagicMock(), "http://localhost"
        )

        assert manager._map_severity_to_priority("critical") == "Highest"
        assert manager._map_severity_to_priority("high") == "High"
        assert manager._map_severity_to_priority("medium") == "Medium"
        assert manager._map_severity_to_priority("low") == "Low"
        assert manager._map_severity_to_priority("unknown") == "Medium"


class TestJiraWebhookHandler:
    @pytest.mark.asyncio
    async def test_handle_issue_updated(self):
        """Test handling issue updated webhook."""
        from aswa_integrations.jira.webhook_handler import (
            JiraWebhookHandler,
            JiraWebhookEvent,
        )

        sync_manager = MagicMock()
        sync_manager.sync_issue = AsyncMock(return_value=MagicMock(
            status=SyncStatus.SYNCED,
            changes={"status": "Done"},
        ))

        handler = JiraWebhookHandler(sync_manager)

        event = JiraWebhookEvent(
            timestamp=1234567890,
            webhookEvent="jira:issue_updated",
            issue={"key": "TEST-123"},
        )

        result = await handler.handle_webhook("tenant-123", event)

        assert result["status"] == "synced"
        sync_manager.sync_issue.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_unhandled_event(self):
        """Test handling unhandled webhook event."""
        from aswa_integrations.jira.webhook_handler import (
            JiraWebhookHandler,
            JiraWebhookEvent,
        )

        sync_manager = MagicMock()
        handler = JiraWebhookHandler(sync_manager)

        event = JiraWebhookEvent(
            timestamp=1234567890,
            webhookEvent="unknown_event",
        )

        result = await handler.handle_webhook("tenant-123", event)

        assert result["status"] == "ignored"
        assert result["reason"] == "unhandled_event_type"

    def test_validate_signature_no_secret(self):
        """Test signature validation when no secret configured."""
        from aswa_integrations.jira.webhook_handler import JiraWebhookHandler

        handler = JiraWebhookHandler(MagicMock(), webhook_secret=None)

        # Should return True when no secret is configured
        assert handler.validate_signature(b"payload", "any_signature") is True

    def test_validate_signature_valid(self):
        """Test valid signature validation."""
        import hmac
        import hashlib
        from aswa_integrations.jira.webhook_handler import JiraWebhookHandler

        secret = "test-secret"
        payload = b'{"test": "data"}'
        expected_sig = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()

        handler = JiraWebhookHandler(MagicMock(), webhook_secret=secret)

        assert handler.validate_signature(payload, expected_sig) is True

    def test_validate_signature_invalid(self):
        """Test invalid signature validation."""
        from aswa_integrations.jira.webhook_handler import JiraWebhookHandler

        handler = JiraWebhookHandler(MagicMock(), webhook_secret="test-secret")

        assert handler.validate_signature(b"payload", "invalid_sig") is False
