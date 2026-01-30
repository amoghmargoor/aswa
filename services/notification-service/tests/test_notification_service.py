import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from aswa_notifications.services.notification_service import NotificationService
from aswa_notifications.models.notification import (
    NotificationCreate,
    NotificationType,
    NotificationChannel,
    NotificationPriority,
)


class TestNotificationService:
    @pytest.fixture
    def service(self):
        return NotificationService()

    @pytest.mark.asyncio
    async def test_should_send_enabled(self, service):
        """Test notification allowed when enabled."""
        notification = NotificationCreate(
            user_id="user-123",
            type=NotificationType.INSIGHT_ALERT,
            channel=NotificationChannel.EMAIL,
        )

        preferences = MagicMock()
        preferences.notifications_enabled = True
        preferences.email_enabled = True
        preferences.type_preferences = {}
        preferences.quiet_hours_enabled = False

        assert service._should_send(notification, preferences) is True

    @pytest.mark.asyncio
    async def test_should_not_send_disabled(self, service):
        """Test notification blocked when disabled."""
        notification = NotificationCreate(
            user_id="user-123",
            type=NotificationType.INSIGHT_ALERT,
            channel=NotificationChannel.EMAIL,
        )

        preferences = MagicMock()
        preferences.notifications_enabled = False

        assert service._should_send(notification, preferences) is False

    @pytest.mark.asyncio
    async def test_should_not_send_channel_disabled(self, service):
        """Test notification blocked when channel disabled."""
        notification = NotificationCreate(
            user_id="user-123",
            type=NotificationType.INSIGHT_ALERT,
            channel=NotificationChannel.EMAIL,
        )

        preferences = MagicMock()
        preferences.notifications_enabled = True
        preferences.email_enabled = False

        assert service._should_send(notification, preferences) is False

    @pytest.mark.asyncio
    async def test_should_send_no_preferences(self, service):
        """Test notification allowed when no preferences."""
        notification = NotificationCreate(
            user_id="user-123",
            type=NotificationType.INSIGHT_ALERT,
            channel=NotificationChannel.EMAIL,
        )

        assert service._should_send(notification, None) is True

    @pytest.mark.asyncio
    async def test_should_send_push_disabled(self, service):
        """Test push notification blocked when push disabled."""
        notification = NotificationCreate(
            user_id="user-123",
            type=NotificationType.INSIGHT_ALERT,
            channel=NotificationChannel.PUSH,
        )

        preferences = MagicMock()
        preferences.notifications_enabled = True
        preferences.push_enabled = False

        assert service._should_send(notification, preferences) is False


class TestTemplateService:
    def test_render_template(self):
        """Test template rendering."""
        from aswa_notifications.services.template_service import TemplateService

        service = TemplateService()
        # Would need template files to test fully

    def test_format_date_filter(self):
        """Test date formatting filter."""
        from aswa_notifications.services.template_service import TemplateService

        service = TemplateService()

        date = datetime(2024, 1, 15)
        formatted = service._format_date(date)

        assert "January" in formatted
        assert "15" in formatted
        assert "2024" in formatted

    def test_format_number_filter(self):
        """Test number formatting filter."""
        from aswa_notifications.services.template_service import TemplateService

        service = TemplateService()

        assert service._format_number(1234567) == "1,234,567"
        assert service._format_number(1234.5678, 2) == "1,234.57"


class TestEmailChannel:
    @pytest.mark.asyncio
    async def test_verify_valid_email(self):
        """Test email validation."""
        from aswa_notifications.channels.email import EmailChannel

        channel = EmailChannel(MagicMock())
        result = await channel.verify_recipient({"email": "test@example.com"})
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_invalid_email(self):
        """Test invalid email validation."""
        from aswa_notifications.channels.email import EmailChannel

        channel = EmailChannel(MagicMock())
        result = await channel.verify_recipient({"email": "invalid-email"})
        assert result is False

    @pytest.mark.asyncio
    async def test_verify_missing_email(self):
        """Test missing email validation."""
        from aswa_notifications.channels.email import EmailChannel

        channel = EmailChannel(MagicMock())
        result = await channel.verify_recipient({})
        assert result is False
