"""Tests for connection API endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient

from aswa_connector.framework.models import (
    ConnectorType,
    Connection,
    ConnectionStatus,
    ConnectorDefinition,
)


class TestListConnectors:
    """Tests for listing connectors."""

    def test_list_connectors(
        self, test_client: TestClient, mock_provider: AsyncMock
    ) -> None:
        """Test listing available connectors."""
        mock_provider.list_available_connectors = AsyncMock(
            return_value=[
                ConnectorDefinition(
                    type=ConnectorType.GMAIL,
                    name="Gmail",
                    description="Sync emails",
                    auth_type="oauth",
                    oauth_provider="google",
                    scopes=["gmail.readonly"],
                ),
            ]
        )

        response = test_client.get("/api/v1/connectors")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["type"] == "gmail"
        assert data[0]["auth_type"] == "oauth"


class TestCreateConnection:
    """Tests for creating connections."""

    def test_create_connection(
        self,
        test_client: TestClient,
        mock_provider: AsyncMock,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test creating a connection."""
        from datetime import datetime, timezone

        connection_id = uuid4()
        mock_provider.create_connection = AsyncMock(
            return_value=Connection(
                id=connection_id,
                tenant_id=uuid4(),
                connector_type=ConnectorType.GMAIL,
                name="My Gmail",
                status=ConnectionStatus.PENDING,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                provider_source_id="src_123",
            )
        )

        # Mock DB operations
        mock_db_session.flush = AsyncMock()
        mock_db_session.refresh = AsyncMock()

        response = test_client.post(
            "/api/v1/connections",
            json={
                "connector_type": "gmail",
                "name": "My Gmail",
                "credentials": {
                    "access_token": "test-token",
                    "refresh_token": "test-refresh",
                },
                "config": {},
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My Gmail"
        assert data["connector_type"] == "gmail"

    def test_create_connection_invalid_type(self, test_client: TestClient) -> None:
        """Test creating connection with invalid type."""
        response = test_client.post(
            "/api/v1/connections",
            json={
                "connector_type": "invalid_type",
                "name": "Test",
                "credentials": {"access_token": "token"},
            },
        )

        assert response.status_code == 400


class TestListConnections:
    """Tests for listing connections."""

    def test_list_connections_empty(
        self, test_client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test listing connections when empty."""
        mock_result = AsyncMock()
        mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        mock_db_session.execute = AsyncMock(
            side_effect=[
                AsyncMock(scalar=MagicMock(return_value=0)),  # Count
                mock_result,  # Results
            ]
        )

        response = test_client.get("/api/v1/connections")

        assert response.status_code == 200
        data = response.json()
        assert data["content"] == []
        assert data["total_elements"] == 0


class TestConnectionTest:
    """Tests for testing connections."""

    def test_connection_not_found(
        self, test_client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test testing non-existent connection."""
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = test_client.post(f"/api/v1/connections/{uuid4()}/test")

        assert response.status_code == 404
