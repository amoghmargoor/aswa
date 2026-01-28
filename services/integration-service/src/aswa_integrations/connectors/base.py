from abc import ABC, abstractmethod
from typing import Any
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
import structlog

logger = structlog.get_logger()


class BaseConnector(ABC):
    """Base class for integration connectors."""

    def __init__(
        self,
        config: dict[str, Any],
        credentials: dict[str, str] | None = None,
    ):
        """Initialize connector.

        Args:
            config: Connector configuration
            credentials: Optional credentials
        """
        self.config = config
        self.credentials = credentials or {}
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        """Context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.disconnect()

    async def connect(self) -> None:
        """Establish connection."""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
        )

    async def disconnect(self) -> None:
        """Close connection."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @abstractmethod
    async def test_connection(self) -> bool:
        """Test the connection.

        Returns:
            True if connection is successful

        Raises:
            Exception if connection fails
        """
        pass

    @abstractmethod
    async def execute(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute an action.

        Args:
            action: Action to execute
            payload: Action payload

        Returns:
            Action result
        """
        pass

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def _request(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> httpx.Response:
        """Make an HTTP request with retry logic.

        Args:
            method: HTTP method
            url: Request URL
            **kwargs: Additional request arguments

        Returns:
            HTTP response
        """
        if not self._client:
            await self.connect()

        response = await self._client.request(method, url, **kwargs)
        response.raise_for_status()
        return response
