# Task 6.3.3: Notification Service - Push Notifications

## Context

You are working on the ASWA notification service at `/services/notification-service/`. Email notifications are complete (Task 6.3.2). Now we need to implement push notifications.

## Objective

Create push notification handling that:
1. Supports FCM for Android/Web
2. Supports APNs for iOS
3. Manages device tokens
4. Handles notification payloads
5. Tracks delivery status

## Requirements

### 1. Create `/services/notification-service/src/aswa_notifications/channels/push.py`
```python
from typing import Any
import httpx
import json
import jwt
import time
import structlog

from aswa_notifications.channels.base import BaseChannel
from aswa_notifications.config import Settings

logger = structlog.get_logger()


class PushChannel(BaseChannel):
    """Push notification channel supporting FCM and APNs."""

    def __init__(self, settings: Settings):
        """Initialize push channel.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self._fcm_initialized = False
        self._apns_initialized = False

    async def send(
        self,
        recipient: dict[str, Any],
        subject: str | None,
        content: dict[str, Any],
        priority: str,
    ) -> dict[str, Any]:
        """Send push notifications to all registered devices.

        Args:
            recipient: Recipient info with 'tokens' list
            subject: Notification title
            content: Notification content with 'body' key
            priority: Notification priority

        Returns:
            Send results
        """
        tokens = recipient.get("tokens", [])
        if not tokens:
            raise ValueError("No push tokens provided")

        results = {
            "sent": 0,
            "failed": 0,
            "message_ids": [],
            "errors": [],
        }

        for token_info in tokens:
            token = token_info.get("token") if isinstance(token_info, dict) else token_info
            platform = token_info.get("platform", "fcm") if isinstance(token_info, dict) else "fcm"

            try:
                if platform == "apns":
                    message_id = await self._send_apns(
                        token=token,
                        title=subject or "Notification",
                        body=content.get("body", ""),
                        data=content.get("data", {}),
                        priority=priority,
                    )
                else:
                    message_id = await self._send_fcm(
                        token=token,
                        title=subject or "Notification",
                        body=content.get("body", ""),
                        data=content.get("data", {}),
                        priority=priority,
                    )

                results["sent"] += 1
                results["message_ids"].append(message_id)

            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "token": token[:20] + "...",
                    "error": str(e),
                })
                logger.error("Push send failed", error=str(e))

        return results

    async def verify_recipient(
        self,
        recipient: dict[str, Any],
    ) -> bool:
        """Verify push tokens are present.

        Args:
            recipient: Recipient info

        Returns:
            True if valid
        """
        tokens = recipient.get("tokens", [])
        return len(tokens) > 0

    async def _send_fcm(
        self,
        token: str,
        title: str,
        body: str,
        data: dict[str, Any],
        priority: str,
    ) -> str:
        """Send notification via Firebase Cloud Messaging.

        Args:
            token: FCM device token
            title: Notification title
            body: Notification body
            data: Custom data payload
            priority: Notification priority

        Returns:
            Message ID
        """
        access_token = await self._get_fcm_access_token()

        fcm_priority = "high" if priority in ("urgent", "high") else "normal"

        message = {
            "message": {
                "token": token,
                "notification": {
                    "title": title,
                    "body": body,
                },
                "data": {k: str(v) for k, v in data.items()},  # FCM requires string values
                "android": {
                    "priority": fcm_priority,
                    "notification": {
                        "click_action": "FLUTTER_NOTIFICATION_CLICK",
                        "channel_id": "aswa_notifications",
                    },
                },
                "webpush": {
                    "headers": {
                        "Urgency": fcm_priority,
                    },
                    "notification": {
                        "icon": "/icon-192.png",
                        "badge": "/badge-72.png",
                    },
                },
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://fcm.googleapis.com/v1/projects/{project}/messages:send",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json=message,
            )

            if not response.is_success:
                error_data = response.json()
                raise Exception(f"FCM error: {error_data}")

            result = response.json()
            return result.get("name", "")

    async def _send_apns(
        self,
        token: str,
        title: str,
        body: str,
        data: dict[str, Any],
        priority: str,
    ) -> str:
        """Send notification via Apple Push Notification Service.

        Args:
            token: APNs device token
            title: Notification title
            body: Notification body
            data: Custom data payload
            priority: Notification priority

        Returns:
            Message ID
        """
        jwt_token = self._generate_apns_token()

        apns_priority = "10" if priority in ("urgent", "high") else "5"

        payload = {
            "aps": {
                "alert": {
                    "title": title,
                    "body": body,
                },
                "sound": "default",
                "badge": 1,
            },
            **data,
        }

        # Use production or sandbox based on environment
        host = (
            "api.push.apple.com"
            if self.settings.environment == "production"
            else "api.sandbox.push.apple.com"
        )

        async with httpx.AsyncClient(http2=True) as client:
            response = await client.post(
                f"https://{host}/3/device/{token}",
                headers={
                    "Authorization": f"bearer {jwt_token}",
                    "apns-topic": self.settings.apns_topic,
                    "apns-priority": apns_priority,
                    "apns-push-type": "alert",
                },
                json=payload,
            )

            if not response.is_success:
                error_data = response.json()
                raise Exception(f"APNs error: {error_data}")

            return response.headers.get("apns-id", "")

    async def _get_fcm_access_token(self) -> str:
        """Get FCM access token using service account.

        Returns:
            Access token
        """
        if not self.settings.firebase_credentials_path:
            raise ValueError("Firebase credentials not configured")

        # Load service account credentials
        with open(self.settings.firebase_credentials_path) as f:
            credentials = json.load(f)

        # Generate JWT
        now = int(time.time())
        payload = {
            "iss": credentials["client_email"],
            "scope": "https://www.googleapis.com/auth/firebase.messaging",
            "aud": "https://oauth2.googleapis.com/token",
            "iat": now,
            "exp": now + 3600,
        }

        signed_jwt = jwt.encode(
            payload,
            credentials["private_key"],
            algorithm="RS256",
        )

        # Exchange JWT for access token
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": signed_jwt,
                },
            )

            if not response.is_success:
                raise Exception("Failed to get FCM access token")

            return response.json()["access_token"]

    def _generate_apns_token(self) -> str:
        """Generate APNs JWT token.

        Returns:
            JWT token
        """
        if not self.settings.apns_key_path:
            raise ValueError("APNs key not configured")

        with open(self.settings.apns_key_path) as f:
            key = f.read()

        now = int(time.time())
        headers = {
            "alg": "ES256",
            "kid": self.settings.apns_key_id,
        }
        payload = {
            "iss": self.settings.apns_team_id,
            "iat": now,
        }

        return jwt.encode(payload, key, algorithm="ES256", headers=headers)


class PushPayloadBuilder:
    """Builds push notification payloads."""

    @classmethod
    def insight_alert(
        cls,
        insight_id: str,
        insight_title: str,
        insight_type: str,
        severity: str,
    ) -> dict[str, Any]:
        """Build insight alert payload.

        Args:
            insight_id: Insight identifier
            insight_title: Insight title
            insight_type: Type (risk/opportunity)
            severity: Severity level

        Returns:
            Push payload
        """
        icon = "⚠️" if insight_type == "risk" else "💡"

        return {
            "title": f"{icon} New {insight_type.title()}",
            "body": insight_title,
            "data": {
                "type": "insight_alert",
                "insight_id": insight_id,
                "insight_type": insight_type,
                "severity": severity,
                "action": "view_insight",
            },
        }

    @classmethod
    def document_processed(
        cls,
        document_id: str,
        document_name: str,
        insight_count: int,
    ) -> dict[str, Any]:
        """Build document processed payload.

        Args:
            document_id: Document identifier
            document_name: Document name
            insight_count: Number of insights

        Returns:
            Push payload
        """
        return {
            "title": "✅ Document Processed",
            "body": f"{document_name} - {insight_count} insights found",
            "data": {
                "type": "document_processed",
                "document_id": document_id,
                "insight_count": insight_count,
                "action": "view_document",
            },
        }

    @classmethod
    def document_failed(
        cls,
        document_id: str,
        document_name: str,
        error: str,
    ) -> dict[str, Any]:
        """Build document failed payload.

        Args:
            document_id: Document identifier
            document_name: Document name
            error: Error message

        Returns:
            Push payload
        """
        return {
            "title": "❌ Processing Failed",
            "body": f"{document_name} could not be processed",
            "data": {
                "type": "document_failed",
                "document_id": document_id,
                "error": error,
                "action": "view_document",
            },
        }

    @classmethod
    def mention(
        cls,
        from_user: str,
        context: str,
        target_id: str,
        target_type: str,
    ) -> dict[str, Any]:
        """Build mention notification payload.

        Args:
            from_user: Mentioning user name
            context: Context snippet
            target_id: Target item ID
            target_type: Target type (insight, query, etc.)

        Returns:
            Push payload
        """
        return {
            "title": f"💬 {from_user} mentioned you",
            "body": context[:100] + "..." if len(context) > 100 else context,
            "data": {
                "type": "mention",
                "target_id": target_id,
                "target_type": target_type,
                "action": "view_mention",
            },
        }


class DeviceTokenManager:
    """Manages device push tokens."""

    def __init__(self, session_factory):
        """Initialize token manager.

        Args:
            session_factory: Database session factory
        """
        self.session_factory = session_factory

    async def register_token(
        self,
        tenant_id: str,
        user_id: str,
        token: str,
        platform: str,
        device_info: dict[str, Any] | None = None,
    ) -> None:
        """Register a device push token.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            token: Push token
            platform: Platform (fcm, apns)
            device_info: Optional device information
        """
        from aswa_notifications.models.preference import NotificationPreferenceDB
        from sqlalchemy import select

        async with self.session_factory() as session:
            result = await session.execute(
                select(NotificationPreferenceDB).where(
                    NotificationPreferenceDB.tenant_id == tenant_id,
                    NotificationPreferenceDB.user_id == user_id,
                )
            )
            preference = result.scalar_one_or_none()

            if not preference:
                # Create preferences if not exist
                preference = NotificationPreferenceDB(
                    tenant_id=tenant_id,
                    user_id=user_id,
                )
                session.add(preference)

            # Update tokens
            tokens = preference.push_tokens or []
            token_entry = {
                "token": token,
                "platform": platform,
                "device_info": device_info or {},
                "registered_at": time.time(),
            }

            # Remove existing token if present
            tokens = [t for t in tokens if t.get("token") != token]
            tokens.append(token_entry)

            preference.push_tokens = tokens

            await session.commit()

        logger.info(
            "Push token registered",
            user_id=user_id,
            platform=platform,
        )

    async def unregister_token(
        self,
        tenant_id: str,
        user_id: str,
        token: str,
    ) -> None:
        """Unregister a device push token.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            token: Push token to remove
        """
        from aswa_notifications.models.preference import NotificationPreferenceDB
        from sqlalchemy import select

        async with self.session_factory() as session:
            result = await session.execute(
                select(NotificationPreferenceDB).where(
                    NotificationPreferenceDB.tenant_id == tenant_id,
                    NotificationPreferenceDB.user_id == user_id,
                )
            )
            preference = result.scalar_one_or_none()

            if preference and preference.push_tokens:
                tokens = [t for t in preference.push_tokens if t.get("token") != token]
                preference.push_tokens = tokens
                await session.commit()

        logger.info("Push token unregistered", user_id=user_id)

    async def get_user_tokens(
        self,
        tenant_id: str,
        user_id: str,
    ) -> list[dict[str, Any]]:
        """Get all tokens for a user.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier

        Returns:
            List of token entries
        """
        from aswa_notifications.models.preference import NotificationPreferenceDB
        from sqlalchemy import select

        async with self.session_factory() as session:
            result = await session.execute(
                select(NotificationPreferenceDB).where(
                    NotificationPreferenceDB.tenant_id == tenant_id,
                    NotificationPreferenceDB.user_id == user_id,
                )
            )
            preference = result.scalar_one_or_none()

            if preference:
                return preference.push_tokens or []
            return []

    async def cleanup_invalid_tokens(
        self,
        tenant_id: str,
        invalid_tokens: list[str],
    ) -> int:
        """Remove invalid tokens from all users.

        Args:
            tenant_id: Tenant identifier
            invalid_tokens: List of invalid token strings

        Returns:
            Number of tokens removed
        """
        from aswa_notifications.models.preference import NotificationPreferenceDB
        from sqlalchemy import select

        count = 0

        async with self.session_factory() as session:
            result = await session.execute(
                select(NotificationPreferenceDB).where(
                    NotificationPreferenceDB.tenant_id == tenant_id,
                )
            )
            preferences = result.scalars().all()

            for preference in preferences:
                if preference.push_tokens:
                    original_count = len(preference.push_tokens)
                    preference.push_tokens = [
                        t for t in preference.push_tokens
                        if t.get("token") not in invalid_tokens
                    ]
                    count += original_count - len(preference.push_tokens)

            await session.commit()

        logger.info("Cleaned up invalid tokens", count=count)
        return count
```

### 2. Create `/services/notification-service/src/aswa_notifications/services/push_service.py`
```python
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
```

### 3. Create `/services/notification-service/src/aswa_notifications/api/push_routes.py`
```python
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated
from pydantic import BaseModel
import structlog

from aswa_notifications.channels.push import DeviceTokenManager
from aswa_notifications.api.dependencies import get_tenant_id, get_user_id

logger = structlog.get_logger()
router = APIRouter(prefix="/push", tags=["push"])

_token_manager: DeviceTokenManager | None = None


def set_token_manager(manager: DeviceTokenManager) -> None:
    """Set the global token manager instance."""
    global _token_manager
    _token_manager = manager


def get_token_manager() -> DeviceTokenManager:
    """Get the token manager dependency."""
    if not _token_manager:
        raise RuntimeError("Token manager not initialized")
    return _token_manager


class RegisterTokenRequest(BaseModel):
    """Request to register a push token."""
    token: str
    platform: str  # fcm, apns
    device_name: str | None = None
    device_model: str | None = None
    os_version: str | None = None
    app_version: str | None = None


class UnregisterTokenRequest(BaseModel):
    """Request to unregister a push token."""
    token: str


@router.post("/tokens")
async def register_push_token(
    request: RegisterTokenRequest,
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    user_id: Annotated[str, Depends(get_user_id)],
    manager: Annotated[DeviceTokenManager, Depends(get_token_manager)],
) -> dict:
    """Register a device push token."""
    device_info = {
        "device_name": request.device_name,
        "device_model": request.device_model,
        "os_version": request.os_version,
        "app_version": request.app_version,
    }

    await manager.register_token(
        tenant_id=tenant_id,
        user_id=user_id,
        token=request.token,
        platform=request.platform,
        device_info=device_info,
    )

    return {"status": "registered"}


@router.delete("/tokens")
async def unregister_push_token(
    request: UnregisterTokenRequest,
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    user_id: Annotated[str, Depends(get_user_id)],
    manager: Annotated[DeviceTokenManager, Depends(get_token_manager)],
) -> dict:
    """Unregister a device push token."""
    await manager.unregister_token(
        tenant_id=tenant_id,
        user_id=user_id,
        token=request.token,
    )

    return {"status": "unregistered"}


@router.get("/tokens")
async def list_push_tokens(
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    user_id: Annotated[str, Depends(get_user_id)],
    manager: Annotated[DeviceTokenManager, Depends(get_token_manager)],
) -> list[dict]:
    """List all registered push tokens for the user."""
    tokens = await manager.get_user_tokens(tenant_id, user_id)

    # Don't expose full tokens
    return [
        {
            "platform": t.get("platform"),
            "device_info": t.get("device_info", {}),
            "registered_at": t.get("registered_at"),
            "token_preview": t.get("token", "")[:20] + "...",
        }
        for t in tokens
    ]
```

## Test Requirements

### Create `/services/notification-service/tests/test_push_channel.py`
```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aswa_notifications.channels.push import (
    PushChannel,
    PushPayloadBuilder,
    DeviceTokenManager,
)


class TestPushChannel:
    @pytest.fixture
    def settings(self):
        settings = MagicMock()
        settings.firebase_credentials_path = ""
        settings.apns_key_path = ""
        settings.apns_key_id = ""
        settings.apns_team_id = ""
        settings.environment = "development"
        return settings

    @pytest.fixture
    def channel(self, settings):
        return PushChannel(settings)

    def test_verify_with_tokens(self, channel):
        """Test verification with tokens."""
        assert channel.verify_recipient({"tokens": [{"token": "abc123"}]}) is True

    def test_verify_without_tokens(self, channel):
        """Test verification without tokens."""
        assert channel.verify_recipient({"tokens": []}) is False
        assert channel.verify_recipient({}) is False

    @pytest.mark.asyncio
    async def test_send_no_tokens(self, channel):
        """Test send fails without tokens."""
        with pytest.raises(ValueError, match="No push tokens"):
            await channel.send(
                recipient={"tokens": []},
                subject="Test",
                content={"body": "Test"},
                priority="normal",
            )


class TestPushPayloadBuilder:
    def test_insight_alert_risk(self):
        """Test risk alert payload."""
        payload = PushPayloadBuilder.insight_alert(
            insight_id="insight-123",
            insight_title="Security Risk",
            insight_type="risk",
            severity="critical",
        )

        assert "Risk" in payload["title"]
        assert "Security Risk" in payload["body"]
        assert payload["data"]["type"] == "insight_alert"
        assert payload["data"]["insight_id"] == "insight-123"
        assert payload["data"]["severity"] == "critical"

    def test_insight_alert_opportunity(self):
        """Test opportunity alert payload."""
        payload = PushPayloadBuilder.insight_alert(
            insight_id="insight-456",
            insight_title="Cost Savings",
            insight_type="opportunity",
            severity="high",
        )

        assert "Opportunity" in payload["title"]
        assert "💡" in payload["title"]

    def test_document_processed(self):
        """Test document processed payload."""
        payload = PushPayloadBuilder.document_processed(
            document_id="doc-123",
            document_name="Report.pdf",
            insight_count=15,
        )

        assert "Processed" in payload["title"]
        assert "Report.pdf" in payload["body"]
        assert "15" in payload["body"]
        assert payload["data"]["action"] == "view_document"

    def test_document_failed(self):
        """Test document failed payload."""
        payload = PushPayloadBuilder.document_failed(
            document_id="doc-456",
            document_name="Bad.pdf",
            error="File corrupted",
        )

        assert "Failed" in payload["title"]
        assert "Bad.pdf" in payload["body"]
        assert payload["data"]["error"] == "File corrupted"

    def test_mention(self):
        """Test mention payload."""
        payload = PushPayloadBuilder.mention(
            from_user="John Doe",
            context="Hey, check this insight about revenue",
            target_id="insight-789",
            target_type="insight",
        )

        assert "John Doe" in payload["title"]
        assert "mentioned" in payload["title"]
        assert "revenue" in payload["body"]


class TestDeviceTokenManager:
    @pytest.fixture
    def session_factory(self):
        return MagicMock()

    @pytest.fixture
    def manager(self, session_factory):
        return DeviceTokenManager(session_factory)

    @pytest.mark.asyncio
    async def test_register_token(self, manager):
        """Test token registration."""
        # Would require database setup for full test
        pass

    @pytest.mark.asyncio
    async def test_unregister_token(self, manager):
        """Test token unregistration."""
        # Would require database setup for full test
        pass
```

## Verification

1. Run tests: `pytest tests/test_push_channel.py -v`
2. Test FCM sending with Firebase project
3. Test APNs sending with Apple credentials
4. Verify payload structure
5. Test token management
