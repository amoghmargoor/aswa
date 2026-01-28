import uuid
from datetime import datetime, timedelta
from typing import Any
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
import structlog

from aswa_notifications.config import get_settings
from aswa_notifications.models.notification import (
    NotificationDB,
    NotificationCreate,
    NotificationBatch,
    NotificationResponse,
    NotificationType,
    NotificationChannel,
    DeliveryStatus,
    Base,
)
from aswa_notifications.models.preference import NotificationPreferenceDB
from aswa_notifications.services.template_service import TemplateService
from aswa_notifications.channels.base import BaseChannel
from aswa_notifications.channels.email import EmailChannel
from aswa_notifications.channels.push import PushChannel

logger = structlog.get_logger()


class NotificationService:
    """Core notification service."""

    def __init__(self):
        self.settings = get_settings()
        self.template_service = TemplateService()
        self._engine = None
        self._session_factory = None
        self._channels: dict[NotificationChannel, BaseChannel] = {}

    async def initialize(self) -> None:
        """Initialize the notification service."""
        self._engine = create_async_engine(
            self.settings.database_url,
            echo=self.settings.debug,
        )

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        self.template_service.initialize()

        # Initialize channels
        self._channels[NotificationChannel.EMAIL] = EmailChannel(self.settings)
        self._channels[NotificationChannel.PUSH] = PushChannel(self.settings)

        logger.info("Notification service initialized")

    async def close(self) -> None:
        """Close connections."""
        if self._engine:
            await self._engine.dispose()

    def _get_session(self) -> AsyncSession:
        """Get a database session."""
        if not self._session_factory:
            raise RuntimeError("Notification service not initialized")
        return self._session_factory()

    async def send(
        self,
        tenant_id: str,
        notification: NotificationCreate,
    ) -> NotificationResponse:
        """Send a notification.

        Args:
            tenant_id: Tenant identifier
            notification: Notification to send

        Returns:
            Created notification
        """
        # Check user preferences
        preferences = await self._get_preferences(tenant_id, notification.user_id)

        if not self._should_send(notification, preferences):
            logger.debug(
                "Notification suppressed by preferences",
                user_id=notification.user_id,
                type=notification.type,
            )
            return None

        # Render content if using template
        content = notification.content or {}
        if notification.template_id:
            rendered = self.template_service.render(
                notification.template_id,
                notification.template_data,
                notification.channel.value,
            )
            content = {
                "subject": rendered.get("subject"),
                "body": rendered.get("body"),
                "html": rendered.get("html"),
            }

        # Create notification record
        notif = NotificationDB(
            tenant_id=tenant_id,
            user_id=notification.user_id,
            type=notification.type,
            channel=notification.channel,
            priority=notification.priority,
            subject=content.get("subject") or notification.subject,
            content=content,
            template_id=notification.template_id,
            template_data=notification.template_data,
            scheduled_at=notification.scheduled_at,
            metadata=notification.metadata,
        )

        async with self._get_session() as session:
            session.add(notif)
            await session.commit()
            await session.refresh(notif)

        # Send immediately if not scheduled
        if not notification.scheduled_at or notification.scheduled_at <= datetime.utcnow():
            await self._deliver(notif, preferences)

        return NotificationResponse.model_validate(notif)

    async def send_batch(
        self,
        tenant_id: str,
        batch: NotificationBatch,
    ) -> list[NotificationResponse]:
        """Send notifications to multiple users.

        Args:
            tenant_id: Tenant identifier
            batch: Batch notification request

        Returns:
            List of created notifications
        """
        results = []

        for user_id in batch.user_ids:
            for channel in batch.channels:
                notification = NotificationCreate(
                    user_id=user_id,
                    type=batch.type,
                    channel=channel,
                    priority=batch.priority,
                    subject=batch.subject,
                    template_id=batch.template_id,
                    template_data=batch.template_data,
                    metadata=batch.metadata,
                )

                result = await self.send(tenant_id, notification)
                if result:
                    results.append(result)

        return results

    async def get_notifications(
        self,
        tenant_id: str,
        user_id: str,
        channel: NotificationChannel | None = None,
        status: DeliveryStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[NotificationResponse]:
        """Get notifications for a user.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            channel: Optional channel filter
            status: Optional status filter
            limit: Maximum results
            offset: Result offset

        Returns:
            List of notifications
        """
        async with self._get_session() as session:
            query = select(NotificationDB).where(
                NotificationDB.tenant_id == tenant_id,
                NotificationDB.user_id == user_id,
            )

            if channel:
                query = query.where(NotificationDB.channel == channel)
            if status:
                query = query.where(NotificationDB.status == status)

            query = query.order_by(NotificationDB.created_at.desc())
            query = query.limit(limit).offset(offset)

            result = await session.execute(query)
            notifications = result.scalars().all()

            return [NotificationResponse.model_validate(n) for n in notifications]

    async def mark_as_read(
        self,
        tenant_id: str,
        user_id: str,
        notification_ids: list[str],
    ) -> int:
        """Mark notifications as read.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            notification_ids: Notification IDs to mark

        Returns:
            Number of notifications updated
        """
        async with self._get_session() as session:
            result = await session.execute(
                update(NotificationDB)
                .where(
                    NotificationDB.tenant_id == tenant_id,
                    NotificationDB.user_id == user_id,
                    NotificationDB.id.in_(notification_ids),
                    NotificationDB.read_at.is_(None),
                )
                .values(read_at=datetime.utcnow())
            )
            await session.commit()
            return result.rowcount

    async def get_unread_count(
        self,
        tenant_id: str,
        user_id: str,
    ) -> int:
        """Get unread notification count.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier

        Returns:
            Unread count
        """
        from sqlalchemy import func

        async with self._get_session() as session:
            result = await session.execute(
                select(func.count(NotificationDB.id)).where(
                    NotificationDB.tenant_id == tenant_id,
                    NotificationDB.user_id == user_id,
                    NotificationDB.channel == NotificationChannel.IN_APP,
                    NotificationDB.read_at.is_(None),
                )
            )
            return result.scalar() or 0

    async def retry_failed(self) -> int:
        """Retry failed notifications.

        Returns:
            Number of retries attempted
        """
        async with self._get_session() as session:
            result = await session.execute(
                select(NotificationDB).where(
                    NotificationDB.status == DeliveryStatus.FAILED,
                    NotificationDB.retry_count < NotificationDB.max_retries,
                )
            )
            notifications = result.scalars().all()

        count = 0
        for notif in notifications:
            preferences = await self._get_preferences(notif.tenant_id, notif.user_id)
            await self._deliver(notif, preferences, is_retry=True)
            count += 1

        return count

    async def _deliver(
        self,
        notification: NotificationDB,
        preferences: NotificationPreferenceDB | None,
        is_retry: bool = False,
    ) -> None:
        """Deliver a notification.

        Args:
            notification: Notification to deliver
            preferences: User preferences
            is_retry: Whether this is a retry
        """
        channel = self._channels.get(notification.channel)
        if not channel:
            logger.warning("Channel not available", channel=notification.channel)
            return

        try:
            # Get recipient info
            recipient = await self._get_recipient_info(notification, preferences)

            # Send through channel
            result = await channel.send(
                recipient=recipient,
                subject=notification.subject,
                content=notification.content,
                priority=notification.priority.value,
            )

            # Update notification status
            async with self._get_session() as session:
                await session.execute(
                    update(NotificationDB)
                    .where(NotificationDB.id == notification.id)
                    .values(
                        status=DeliveryStatus.SENT,
                        external_id=result.get("message_id"),
                        sent_at=datetime.utcnow(),
                        retry_count=notification.retry_count + (1 if is_retry else 0),
                    )
                )
                await session.commit()

            logger.info(
                "Notification sent",
                notification_id=str(notification.id),
                channel=notification.channel.value,
            )

        except Exception as e:
            logger.error(
                "Notification delivery failed",
                notification_id=str(notification.id),
                error=str(e),
            )

            async with self._get_session() as session:
                await session.execute(
                    update(NotificationDB)
                    .where(NotificationDB.id == notification.id)
                    .values(
                        status=DeliveryStatus.FAILED,
                        error=str(e),
                        retry_count=notification.retry_count + 1,
                    )
                )
                await session.commit()

    def _should_send(
        self,
        notification: NotificationCreate,
        preferences: NotificationPreferenceDB | None,
    ) -> bool:
        """Check if notification should be sent based on preferences.

        Args:
            notification: Notification to check
            preferences: User preferences

        Returns:
            True if should send
        """
        if not preferences:
            return True

        if not preferences.notifications_enabled:
            return False

        # Check channel preference
        channel = notification.channel
        if channel == NotificationChannel.EMAIL and not preferences.email_enabled:
            return False
        if channel == NotificationChannel.PUSH and not preferences.push_enabled:
            return False
        if channel == NotificationChannel.IN_APP and not preferences.in_app_enabled:
            return False

        # Check type preference
        type_prefs = preferences.type_preferences or {}
        if notification.type.value in type_prefs:
            channel_prefs = type_prefs[notification.type.value]
            if channel.value in channel_prefs:
                return channel_prefs[channel.value]

        # Check quiet hours
        if preferences.quiet_hours_enabled:
            if self._is_quiet_hours(preferences):
                # Only suppress non-urgent notifications
                if notification.priority.value != "urgent":
                    return False

        return True

    def _is_quiet_hours(self, preferences: NotificationPreferenceDB) -> bool:
        """Check if currently in quiet hours.

        Args:
            preferences: User preferences

        Returns:
            True if in quiet hours
        """
        from datetime import time
        import pytz

        if not preferences.quiet_hours_start or not preferences.quiet_hours_end:
            return False

        tz = pytz.timezone(preferences.quiet_hours_timezone)
        now = datetime.now(tz).time()

        start = time.fromisoformat(preferences.quiet_hours_start)
        end = time.fromisoformat(preferences.quiet_hours_end)

        if start <= end:
            return start <= now <= end
        else:
            # Overnight quiet hours (e.g., 22:00 - 08:00)
            return now >= start or now <= end

    async def _get_preferences(
        self,
        tenant_id: str,
        user_id: str,
    ) -> NotificationPreferenceDB | None:
        """Get user preferences.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier

        Returns:
            Preferences or None
        """
        async with self._get_session() as session:
            result = await session.execute(
                select(NotificationPreferenceDB).where(
                    NotificationPreferenceDB.tenant_id == tenant_id,
                    NotificationPreferenceDB.user_id == user_id,
                )
            )
            return result.scalar_one_or_none()

    async def _get_recipient_info(
        self,
        notification: NotificationDB,
        preferences: NotificationPreferenceDB | None,
    ) -> dict[str, Any]:
        """Get recipient info for delivery.

        Args:
            notification: Notification
            preferences: User preferences

        Returns:
            Recipient info
        """
        recipient = {"user_id": notification.user_id}

        if preferences:
            if notification.channel == NotificationChannel.EMAIL:
                recipient["email"] = preferences.email_address
            elif notification.channel == NotificationChannel.PUSH:
                recipient["tokens"] = preferences.push_tokens

        return recipient
