import hashlib
import hmac
import time
from typing import Any
import structlog

logger = structlog.get_logger()


class WebhookValidator:
    """Validates incoming webhook requests."""

    def __init__(self, signing_secret: str, tolerance: int = 300):
        """Initialize validator.

        Args:
            signing_secret: Secret for signature validation
            tolerance: Timestamp tolerance in seconds
        """
        self.signing_secret = signing_secret
        self.tolerance = tolerance

    def validate_signature(
        self,
        payload: bytes,
        signature: str,
        timestamp: str | None = None,
    ) -> bool:
        """Validate webhook signature.

        Args:
            payload: Raw request body
            signature: Signature from header
            timestamp: Optional timestamp from header

        Returns:
            True if signature is valid

        Raises:
            ValueError if validation fails
        """
        # Validate timestamp if provided
        if timestamp:
            try:
                ts = int(timestamp)
                if abs(time.time() - ts) > self.tolerance:
                    raise ValueError("Timestamp outside tolerance window")
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid timestamp: {e}")

        # Parse signature
        if signature.startswith("sha256="):
            signature = signature[7:]

        # Compute expected signature
        if timestamp:
            signing_payload = f"{timestamp}:{payload.decode()}"
        else:
            signing_payload = payload.decode()

        expected = hmac.new(
            self.signing_secret.encode(),
            signing_payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        # Constant-time comparison
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid signature")

        return True

    def generate_signature(
        self,
        payload: bytes,
        timestamp: int | None = None,
    ) -> tuple[str, int]:
        """Generate a webhook signature.

        Args:
            payload: Request body
            timestamp: Optional timestamp (defaults to current time)

        Returns:
            Tuple of (signature, timestamp)
        """
        ts = timestamp or int(time.time())
        signing_payload = f"{ts}:{payload.decode()}"

        signature = hmac.new(
            self.signing_secret.encode(),
            signing_payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        return f"sha256={signature}", ts


class InboundWebhookHandler:
    """Handles inbound webhooks from external services."""

    def __init__(self):
        self._handlers: dict[str, callable] = {}

    def register_handler(
        self,
        source: str,
        handler: callable,
    ) -> None:
        """Register a handler for a webhook source.

        Args:
            source: Webhook source identifier
            handler: Async handler function
        """
        self._handlers[source] = handler
        logger.info("Webhook handler registered", source=source)

    async def handle(
        self,
        source: str,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        """Handle an inbound webhook.

        Args:
            source: Webhook source
            payload: Request payload
            headers: Request headers

        Returns:
            Handler response
        """
        handler = self._handlers.get(source)
        if not handler:
            raise ValueError(f"No handler for source: {source}")

        logger.info("Processing inbound webhook", source=source)

        try:
            result = await handler(payload, headers)
            return {"status": "processed", "result": result}
        except Exception as e:
            logger.error(
                "Inbound webhook handler failed",
                source=source,
                error=str(e),
            )
            raise
