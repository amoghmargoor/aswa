from typing import Any
import structlog

from aswa_notifications.channels.push import PushChannel, PushPayloadBuilder
from aswa_notifications.services.notification_service import NotificationService
from aswa_notifications.models.notification import (
    NotificationCreate,
    NotificationType,
    NotificationChannel,
    NotificationPriority,
)

logger = structlog.get_logger()


class PushService:
    """High-level push notification service."""

    def __init__(
        self,
        notification_service: NotificationService,
    ):
        """Initialize push service.

        Args:
            notification_service: Core notification service
        """
        self.notification_service = notification_service

    async def send_insight_alert(
        self,
        tenant_id: str,
        user_id: str,
        insight: dict[str, Any],
    ) -> None:
        """Send insight alert push notification.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            insight: Insight data
        """
        payload = PushPayloadBuilder.insight_alert(
            insight_id=insight.get("id", ""),
            insight_title=insight.get("title", "New Insight"),
            insight_type=insight.get("type", "insight"),
            severity=insight.get("severity", "medium"),
        )

        notification = NotificationCreate(
            user_id=user_id,
            type=NotificationType.INSIGHT_ALERT,
            channel=NotificationChannel.PUSH,
            priority=self._severity_to_priority(insight.get("severity")),
            subject=payload["title"],
            content={
                "body": payload["body"],
                "data": payload["data"],
            },
            metadata={"insight_id": insight.get("id")},
        )

        await self.notification_service.send(tenant_id, notification)

    async def send_document_processed(
        self,
        tenant_id: str,
        user_id: str,
        document: dict[str, Any],
    ) -> None:
        """Send document processed push notification.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            document: Document data
        """
        payload = PushPayloadBuilder.document_processed(
            document_id=document.get("id", ""),
            document_name=document.get("name", "Document"),
            insight_count=document.get("insight_count", 0),
        )

        notification = NotificationCreate(
            user_id=user_id,
            type=NotificationType.DOCUMENT_PROCESSED,
            channel=NotificationChannel.PUSH,
            priority=NotificationPriority.NORMAL,
            subject=payload["title"],
            content={
                "body": payload["body"],
                "data": payload["data"],
            },
            metadata={"document_id": document.get("id")},
        )

        await self.notification_service.send(tenant_id, notification)

    async def send_document_failed(
        self,
        tenant_id: str,
        user_id: str,
        document: dict[str, Any],
        error: str,
    ) -> None:
        """Send document failed push notification.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            document: Document data
            error: Error message
        """
        payload = PushPayloadBuilder.document_failed(
            document_id=document.get("id", ""),
            document_name=document.get("name", "Document"),
            error=error,
        )

        notification = NotificationCreate(
            user_id=user_id,
            type=NotificationType.DOCUMENT_FAILED,
            channel=NotificationChannel.PUSH,
            priority=NotificationPriority.HIGH,
            subject=payload["title"],
            content={
                "body": payload["body"],
                "data": payload["data"],
            },
            metadata={"document_id": document.get("id")},
        )

        await self.notification_service.send(tenant_id, notification)

    async def send_mention(
        self,
        tenant_id: str,
        user_id: str,
        from_user: str,
        context: str,
        target_id: str,
        target_type: str,
    ) -> None:
        """Send mention push notification.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            from_user: Mentioning user name
            context: Context snippet
            target_id: Target item ID
            target_type: Target type
        """
        payload = PushPayloadBuilder.mention(
            from_user=from_user,
            context=context,
            target_id=target_id,
            target_type=target_type,
        )

        notification = NotificationCreate(
            user_id=user_id,
            type=NotificationType.MENTION,
            channel=NotificationChannel.PUSH,
            priority=NotificationPriority.NORMAL,
            subject=payload["title"],
            content={
                "body": payload["body"],
                "data": payload["data"],
            },
        )

        await self.notification_service.send(tenant_id, notification)

    async def send_to_all_devices(
        self,
        tenant_id: str,
        user_id: str,
        title: str,
        body: str,
        data: dict[str, Any] | None = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
    ) -> None:
        """Send custom push to all user devices.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            title: Notification title
            body: Notification body
            data: Optional custom data
            priority: Notification priority
        """
        notification = NotificationCreate(
            user_id=user_id,
            type=NotificationType.SYSTEM_ALERT,
            channel=NotificationChannel.PUSH,
            priority=priority,
            subject=title,
            content={
                "body": body,
                "data": data or {},
            },
        )

        await self.notification_service.send(tenant_id, notification)

    def _severity_to_priority(
        self,
        severity: str | None,
    ) -> NotificationPriority:
        """Map severity to notification priority.

        Args:
            severity: Insight severity

        Returns:
            Notification priority
        """
        mapping = {
            "critical": NotificationPriority.URGENT,
            "high": NotificationPriority.HIGH,
            "medium": NotificationPriority.NORMAL,
            "low": NotificationPriority.LOW,
        }
        return mapping.get(severity or "medium", NotificationPriority.NORMAL)
