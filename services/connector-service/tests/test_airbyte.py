"""Tests for Airbyte provider."""

import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from aswa_connector.providers.airbyte.client import AirbyteClient
from aswa_connector.providers.airbyte.provider import AirbyteProvider
from aswa_connector.providers.airbyte.source_configs import (
    get_connector_definition,
    get_all_connector_definitions,
    build_source_config,
)
from aswa_connector.framework.models import ConnectorType, ConnectionConfig, OAuthCredentials


class TestAirbyteClient:
    """Tests for Airbyte API client."""

    @pytest.fixture
    def client(self) -> AirbyteClient:
        """Create Airbyte client."""
        return AirbyteClient(api_url="http://localhost:8001")

    @pytest.mark.asyncio
    async def test_health_check_success(self, client: AirbyteClient) -> None:
        """Test health check succeeds."""
        with patch.object(client, "_get_client") as mock_get:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=AsyncMock(status_code=200))
            mock_get.return_value = mock_http

            result = await client.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, client: AirbyteClient) -> None:
        """Test health check fails gracefully."""
        with patch.object(client, "_get_client") as mock_get:
            mock_get.side_effect = Exception("Connection failed")

            result = await client.health_check()
            assert result is False


class TestSourceConfigs:
    """Tests for source configuration builders."""

    def test_get_connector_definition(self) -> None:
        """Test getting connector definitions."""
        gmail = get_connector_definition(ConnectorType.GMAIL)
        assert gmail is not None
        assert gmail.type == ConnectorType.GMAIL
        assert gmail.auth_type == "oauth"
        assert gmail.oauth_provider == "google"

    def test_get_all_definitions(self) -> None:
        """Test getting all connector definitions."""
        definitions = get_all_connector_definitions()
        assert len(definitions) >= 4
        types = [d.type for d in definitions]
        assert ConnectorType.GMAIL in types
        assert ConnectorType.SLACK in types

    def test_build_gmail_config(self) -> None:
        """Test building Gmail source config."""
        credentials = {
            "access_token": "test-token",
            "refresh_token": "test-refresh",
        }
        config = {"include_labels": ["INBOX"]}

        result = build_source_config(ConnectorType.GMAIL, credentials, config)

        assert "credentials" in result
        assert result["credentials"]["access_token"] == "test-token"
        assert result["include_labels"] == ["INBOX"]

    def test_build_slack_config(self) -> None:
        """Test building Slack source config."""
        credentials = {"access_token": "xoxb-token"}
        config = {"channel_filter": ["general"], "lookback_days": 30}

        result = build_source_config(ConnectorType.SLACK, credentials, config)

        assert result["credentials"]["access_token"] == "xoxb-token"
        assert result["lookback_window"] == 30


class TestAirbyteProvider:
    """Tests for Airbyte provider."""

    @pytest.fixture
    def provider(self) -> AirbyteProvider:
        """Create Airbyte provider."""
        return AirbyteProvider()

    def test_provider_name(self, provider: AirbyteProvider) -> None:
        """Test provider name."""
        assert provider.name == "airbyte"

    @pytest.mark.asyncio
    async def test_list_connectors(self, provider: AirbyteProvider) -> None:
        """Test listing available connectors."""
        connectors = await provider.list_available_connectors()

        assert len(connectors) >= 4
        types = [c.type for c in connectors]
        assert ConnectorType.GMAIL in types

    @pytest.mark.asyncio
    async def test_get_connector_definition(self, provider: AirbyteProvider) -> None:
        """Test getting connector definition."""
        definition = await provider.get_connector_definition("gmail")

        assert definition is not None
        assert definition.type == ConnectorType.GMAIL

    @pytest.mark.asyncio
    async def test_get_unknown_connector(self, provider: AirbyteProvider) -> None:
        """Test getting unknown connector returns None."""
        definition = await provider.get_connector_definition("unknown")
        assert definition is None
