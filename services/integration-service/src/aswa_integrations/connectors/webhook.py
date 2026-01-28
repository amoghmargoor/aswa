from typing import Any
import hashlib
import hmac
import json
import structlog

from aswa_integrations.connectors.base import BaseConnector

logger = structlog.get_logger()


class WebhookConnector(BaseConnector):
    """Generic webhook connector."""

    def __init__(
        self,
        config: dict[str, Any],
        credentials: dict[str, str] | None = None,
    ):
        super().__init__(config, credentials)
        self.url = config.get("url", "")
        self.method = config.get("method", "POST").upper()
        self.headers = config.get("headers", {})
        self.signing_secret = credentials.get("signing_secret") if credentials else None

    async def test_connection(self) -> bool:
        """Test webhook endpoint.

        Returns:
            True if endpoint is reachable

        Raises:
            Exception if endpoint is not reachable
        """
        # Send a test ping
        test_payload = {"type": "test", "message": "ASWA webhook test"}

        headers = self._build_headers(test_payload)
        response = await self._request(
            self.method,
            self.url,
            headers=headers,
            json=test_payload,
        )

        logger.info(
            "Webhook connection test successful",
            url=self.url,
            status=response.status_code,
        )

        return True

    async def execute(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute a webhook action.

        Args:
            action: Action type (send)
            payload: Webhook payload

        Returns:
            Webhook response
        """
        if action != "send":
            raise ValueError(f"Unknown action: {action}")

        return await self._send_webhook(payload)

    async def _send_webhook(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a webhook request.

        Args:
            payload: Request payload

        Returns:
            Response data
        """
        headers = self._build_headers(payload)

        response = await self._request(
            self.method,
            self.url,
            headers=headers,
            json=payload,
        )

        logger.info(
            "Webhook sent",
            url=self.url,
            status=response.status_code,
        )

        # Try to parse JSON response
        try:
            return response.json()
        except Exception:
            return {"status": response.status_code, "body": response.text}

    def _build_headers(self, payload: dict[str, Any]) -> dict[str, str]:
        """Build request headers with optional signing.

        Args:
            payload: Request payload for signing

        Returns:
            Headers dictionary
        """
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "ASWA-Integration/1.0",
            **self.headers,
        }

        # Add signature if signing secret is configured
        if self.signing_secret:
            payload_bytes = json.dumps(payload, sort_keys=True).encode()
            signature = hmac.new(
                self.signing_secret.encode(),
                payload_bytes,
                hashlib.sha256,
            ).hexdigest()
            headers["X-ASWA-Signature"] = f"sha256={signature}"

        return headers
