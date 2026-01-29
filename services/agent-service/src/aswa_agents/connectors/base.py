"""Base class for external system connectors."""

from abc import ABC, abstractmethod
from typing import Any

import httpx
import structlog
from pydantic import BaseModel

logger = structlog.get_logger()


class ConnectorConfig(BaseModel):
    """Base configuration for connectors."""

    enabled: bool = True
    timeout_seconds: int = 30
    max_retries: int = 3


class ConnectorCredentials(BaseModel):
    """Credentials for connector authentication."""

    access_token: str | None = None
    refresh_token: str | None = None
    api_key: str | None = None
    expires_at: int | None = None
    metadata: dict[str, Any] = {}


class Connector(ABC):
    """
    Base class for external system connectors.

    Connectors provide a consistent interface for interacting with
    external systems (Jira, Slack, Zendesk, etc.). They handle:
    1. Authentication (OAuth, API keys)
    2. Rate limiting
    3. Error handling
    4. Retries

    New connectors are added by:
    1. Subclassing Connector
    2. Implementing required methods
    3. Registering with ConnectorRegistry

    Example:
        @ConnectorRegistry.register
        class JiraConnector(Connector):
            id = "jira"
            name = "Jira"

            async def create_issue(self, project, issue_type, summary, ...):
                response = await self._request("POST", "/rest/api/3/issue", data={...})
                return response.json()
    """

    # Connector metadata
    id: str = ""
    name: str = ""
    description: str = ""
    icon: str = "link"
    category: str = "integration"

    # OAuth configuration
    oauth_enabled: bool = False
    oauth_scopes: list[str] = []

    # API configuration
    base_url: str = ""

    def __init__(self, config: ConnectorConfig | None = None):
        """Initialize connector."""
        self.config = config or ConnectorConfig()
        self._credentials: ConnectorCredentials | None = None
        self._client: httpx.AsyncClient | None = None
        self._logger = logger.bind(connector_id=self.id)

    def set_credentials(self, credentials: ConnectorCredentials) -> None:
        """Set connector credentials."""
        self._credentials = credentials

    @property
    def is_authenticated(self) -> bool:
        """Check if connector has valid credentials."""
        return self._credentials is not None and (
            self._credentials.access_token is not None
            or self._credentials.api_key is not None
        )

    async def _get_client(self) -> httpx.AsyncClient:
        """Get HTTP client with authentication."""
        if self._client is None:
            headers = {}
            if self._credentials:
                if self._credentials.access_token:
                    headers["Authorization"] = f"Bearer {self._credentials.access_token}"
                elif self._credentials.api_key:
                    headers["Authorization"] = f"Api-Key {self._credentials.api_key}"

            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=self.config.timeout_seconds,
            )
        return self._client

    async def _request(
        self,
        method: str,
        path: str,
        data: dict | None = None,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> httpx.Response:
        """Make authenticated HTTP request."""
        client = await self._get_client()

        self._logger.debug(
            "Making request",
            method=method,
            path=path,
        )

        response = await client.request(
            method=method,
            url=path,
            json=data,
            params=params,
            headers=headers,
        )
        response.raise_for_status()
        return response

    @abstractmethod
    async def test_connection(self) -> bool:
        """
        Test if the connector can connect to the external system.

        Returns:
            True if connection is successful
        """
        pass

    async def close(self) -> None:
        """Close connector and release resources."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def __repr__(self) -> str:
        return f"Connector({self.id}: {self.name})"
