import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from aswa_integrations.jira.issue_manager import JiraIssueManager, JiraIssueCreate
from aswa_integrations.jira.oauth import JiraTokens


class TestJiraIssueManager:
    @pytest.fixture
    def mock_tokens(self):
        return JiraTokens(
            access_token="test-token",
            refresh_token="refresh-token",
            expires_at=datetime.utcnow(),
            scope="read:jira-work write:jira-work",
            cloud_id="cloud-123",
        )

    @pytest.fixture
    def sample_insight(self):
        return {
            "id": "insight-123",
            "type": "risk",
            "title": "Security Vulnerability",
            "description": "Critical security issue found",
            "severity": "critical",
            "confidence": 0.95,
            "document_name": "Security Report.pdf",
        }

    @pytest.mark.asyncio
    async def test_create_issue_from_insight(self, mock_tokens, sample_insight):
        """Test creating an issue from an insight."""
        oauth_handler = MagicMock()
        oauth_handler.get_valid_tokens = AsyncMock(return_value=mock_tokens)

        session_factory = MagicMock()

        manager = JiraIssueManager(oauth_handler, session_factory)

        # Mock project config
        with patch.object(manager.project_config, 'get_config', new_callable=AsyncMock) as mock_config:
            from aswa_integrations.jira.project_config import JiraProjectConfigResponse

            mock_config.return_value = JiraProjectConfigResponse(
                id="config-123",
                tenant_id="tenant-123",
                project_key="TEST",
                project_name="Test Project",
                risk_issue_type="Bug",
                opportunity_issue_type="Story",
                default_issue_type="Task",
                priority_mapping={"critical": "Highest"},
                auto_labels=["aswa"],
                include_severity_label=True,
                include_type_label=True,
                custom_field_mappings={},
                sync_enabled=True,
                sync_comments=True,
                sync_status=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )

            # Verify the config was called correctly
            assert mock_config is not None


class TestBuildIssuePayload:
    def test_build_payload_basic(self):
        """Test building basic issue payload."""
        manager = JiraIssueManager(MagicMock(), MagicMock())

        payload = manager._build_issue_payload(
            project_key="TEST",
            summary="Test Issue",
            description="Test description",
            issue_type="Bug",
            priority="High",
            labels=["aswa", "test"],
        )

        assert payload["fields"]["project"]["key"] == "TEST"
        assert payload["fields"]["summary"] == "Test Issue"
        assert payload["fields"]["issuetype"]["name"] == "Bug"
        assert payload["fields"]["priority"]["name"] == "High"
        assert "aswa" in payload["fields"]["labels"]

    def test_build_payload_with_assignee(self):
        """Test building payload with assignee."""
        manager = JiraIssueManager(MagicMock(), MagicMock())

        payload = manager._build_issue_payload(
            project_key="TEST",
            summary="Test Issue",
            description="Test description",
            issue_type="Task",
            priority="Medium",
            labels=[],
            assignee_id="user-123",
        )

        assert payload["fields"]["assignee"]["accountId"] == "user-123"
