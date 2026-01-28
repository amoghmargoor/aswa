import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from aswa_integrations.jira.oauth import (
    JiraOAuthHandler,
    JiraOAuthConfig,
    JiraTokens,
)


class TestJiraOAuth:
    @pytest.fixture
    def oauth_config(self):
        return JiraOAuthConfig(
            client_id="test-client-id",
            client_secret="test-client-secret",
            redirect_uri="https://app.aswa.io/jira/callback",
        )

    @pytest.fixture
    def oauth_handler(self, oauth_config):
        credential_manager = MagicMock()
        credential_manager.store_credentials = AsyncMock()
        credential_manager.get_credentials = AsyncMock(return_value=None)
        return JiraOAuthHandler(oauth_config, credential_manager)

    def test_get_authorization_url(self, oauth_handler):
        """Test authorization URL generation."""
        url, state = oauth_handler.get_authorization_url("tenant-123")

        assert "auth.atlassian.com/authorize" in url
        assert "client_id=test-client-id" in url
        assert f"state={state}" in url
        assert len(state) > 20

    @pytest.mark.asyncio
    async def test_exchange_code_invalid_state(self, oauth_handler):
        """Test code exchange with invalid state."""
        with pytest.raises(ValueError, match="Invalid or expired state"):
            await oauth_handler.exchange_code("code123", "invalid-state")

    @pytest.mark.asyncio
    async def test_get_valid_tokens_refresh(self, oauth_handler):
        """Test token refresh when expiring soon."""
        # Mock stored tokens that are about to expire
        expiring_tokens = JiraTokens(
            access_token="old-token",
            refresh_token="refresh-token",
            expires_at=datetime.utcnow() + timedelta(minutes=2),
            scope="read:jira-work",
            cloud_id="cloud-123",
        )

        oauth_handler.credential_manager.get_credentials = AsyncMock(
            return_value={
                "access_token": expiring_tokens.access_token,
                "refresh_token": expiring_tokens.refresh_token,
                "expires_at": expiring_tokens.expires_at.isoformat(),
                "scope": expiring_tokens.scope,
                "cloud_id": expiring_tokens.cloud_id,
            }
        )

        with patch.object(oauth_handler, 'refresh_tokens', new_callable=AsyncMock) as mock_refresh:
            mock_refresh.return_value = JiraTokens(
                access_token="new-token",
                refresh_token="refresh-token",
                expires_at=datetime.utcnow() + timedelta(hours=1),
                scope="read:jira-work",
                cloud_id="cloud-123",
            )

            tokens = await oauth_handler.get_valid_tokens("tenant-123")

            mock_refresh.assert_called_once()
            assert tokens.access_token == "new-token"


class TestJiraFieldMapper:
    def test_map_risk_insight(self):
        """Test mapping risk insight to Jira issue."""
        from aswa_integrations.jira.field_mapper import JiraFieldMapper
        from aswa_integrations.jira.project_config import JiraProjectConfigResponse

        config = JiraProjectConfigResponse(
            id="config-123",
            tenant_id="tenant-123",
            project_key="TEST",
            project_name="Test Project",
            risk_issue_type="Bug",
            opportunity_issue_type="Story",
            default_issue_type="Task",
            priority_mapping={"critical": "Highest", "high": "High"},
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

        mapper = JiraFieldMapper(config)

        insight = {
            "id": "insight-123",
            "type": "risk",
            "title": "Security Vulnerability",
            "description": "Critical security issue found",
            "severity": "critical",
            "confidence": 0.95,
        }

        result = mapper.map_insight_to_issue(insight)

        assert result.issue_type == "Bug"
        assert result.priority == "Highest"
        assert "[RISK]" in result.summary
        assert "severity:critical" in result.labels
        assert "type:risk" in result.labels
