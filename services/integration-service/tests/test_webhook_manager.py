import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from aswa_integrations.services.webhook_manager import WebhookManager
from aswa_integrations.models.webhook import (
    WebhookCreate,
    WebhookEventType,
    WebhookEvent,
)


class TestWebhookManager:
    @pytest.fixture
    def manager(self):
        """Create a webhook manager instance."""
        return WebhookManager()

    @pytest.mark.asyncio
    async def test_dispatch_event(self, manager):
        """Test event dispatching."""
        event = WebhookEvent(
            type=WebhookEventType.INSIGHT_CREATED,
            tenant_id="test-tenant",
            data={"insight_id": "123"},
        )

        with patch.object(manager, '_get_session') as mock_session, \
             patch.object(manager, '_create_delivery', new_callable=AsyncMock) as mock_create:

            session = AsyncMock()
            result = MagicMock()
            result.scalars.return_value.all.return_value = []
            session.execute = AsyncMock(return_value=result)
            mock_session.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_session.return_value.__aexit__ = AsyncMock()

            delivery_ids = await manager.dispatch_event(event)

            assert isinstance(delivery_ids, list)


class TestWebhookValidator:
    def test_validate_signature(self):
        """Test signature validation."""
        from aswa_integrations.services.webhook_validator import WebhookValidator

        validator = WebhookValidator("test-secret")
        payload = b'{"test": "data"}'

        signature, timestamp = validator.generate_signature(payload)

        # Should validate successfully
        result = validator.validate_signature(
            payload,
            signature,
            str(timestamp),
        )

        assert result is True

    def test_invalid_signature(self):
        """Test invalid signature rejection."""
        from aswa_integrations.services.webhook_validator import WebhookValidator

        validator = WebhookValidator("test-secret")
        payload = b'{"test": "data"}'

        with pytest.raises(ValueError, match="Invalid signature"):
            validator.validate_signature(
                payload,
                "sha256=invalid",
            )

    def test_generate_signature(self):
        """Test signature generation."""
        from aswa_integrations.services.webhook_validator import WebhookValidator

        validator = WebhookValidator("test-secret")
        payload = b'{"test": "data"}'

        signature, timestamp = validator.generate_signature(payload)

        assert signature.startswith("sha256=")
        assert isinstance(timestamp, int)
