"""Base HTTP client with retry and observability."""

import httpx

from aswa_common.metrics import MetricsRegistry
from aswa_common.resilience import CircuitBreaker


class BaseHttpClient:
    """Base HTTP client with retry, circuit breaker, and observability."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        circuit_breaker: CircuitBreaker | None = None,
        metrics: MetricsRegistry | None = None,
    ) -> None:
        """Initialize HTTP client.

        Args:
            base_url: Base URL for requests
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries
            circuit_breaker: Optional circuit breaker
            metrics: Optional metrics registry
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.circuit_breaker = circuit_breaker
        self.metrics = metrics
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client.

        Returns:
            Async HTTP client
        """
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
            )
        return self._client

    async def get(
        self,
        path: str,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Send GET request.

        Args:
            path: Request path
            params: Optional query parameters
            headers: Optional headers

        Returns:
            HTTP response
        """
        client = await self._get_client()
        return await client.get(path, params=params, headers=headers)

    async def post(
        self,
        path: str,
        json: dict[str, any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Send POST request.

        Args:
            path: Request path
            json: Optional JSON body
            headers: Optional headers

        Returns:
            HTTP response
        """
        client = await self._get_client()
        return await client.post(path, json=json, headers=headers)

    async def put(
        self,
        path: str,
        json: dict[str, any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Send PUT request.

        Args:
            path: Request path
            json: Optional JSON body
            headers: Optional headers

        Returns:
            HTTP response
        """
        client = await self._get_client()
        return await client.put(path, json=json, headers=headers)

    async def delete(
        self,
        path: str,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Send DELETE request.

        Args:
            path: Request path
            headers: Optional headers

        Returns:
            HTTP response
        """
        client = await self._get_client()
        return await client.delete(path, headers=headers)

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "BaseHttpClient":
        """Enter async context manager.

        Returns:
            Self
        """
        return self

    async def __aexit__(self, *args: any) -> None:
        """Exit async context manager."""
        await self.close()
