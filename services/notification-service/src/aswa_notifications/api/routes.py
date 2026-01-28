from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated
import structlog

from aswa_notifications.models.notification import (
    NotificationCreate,
    NotificationBatch,
    NotificationResponse,
    NotificationChannel,
    DeliveryStatus,
)
from aswa_notifications.models.preference import PreferenceUpdate, PreferenceResponse
from aswa_notifications.services.notification_service import NotificationService
from aswa_notifications.services.preference_service import PreferenceService
from aswa_notifications.api.dependencies import get_tenant_id, get_user_id

logger = structlog.get_logger()
router = APIRouter(tags=["notifications"])

_notification_service: NotificationService | None = None
_preference_service: PreferenceService | None = None


def set_notification_service(service: NotificationService) -> None:
    """Set the global notification service."""
    global _notification_service
    _notification_service = service


def set_preference_service(service: PreferenceService) -> None:
    """Set the global preference service."""
    global _preference_service
    _preference_service = service


def get_notification_service() -> NotificationService:
    """Get the notification service."""
    if not _notification_service:
        raise RuntimeError("Notification service not initialized")
    return _notification_service


def get_preference_service() -> PreferenceService:
    """Get the preference service."""
    if not _preference_service:
        raise RuntimeError("Preference service not initialized")
    return _preference_service


# Notification endpoints

@router.post("/notifications", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
async def send_notification(
    notification: NotificationCreate,
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> NotificationResponse:
    """Send a notification."""
    result = await service.send(tenant_id, notification)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_204_NO_CONTENT,
            detail="Notification suppressed by preferences",
        )
    return result


@router.post("/notifications/batch", response_model=list[NotificationResponse])
async def send_batch(
    batch: NotificationBatch,
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> list[NotificationResponse]:
    """Send notifications to multiple users."""
    return await service.send_batch(tenant_id, batch)


@router.get("/notifications", response_model=list[NotificationResponse])
async def get_notifications(
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
    channel: NotificationChannel | None = None,
    status: DeliveryStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[NotificationResponse]:
    """Get notifications for a user."""
    return await service.get_notifications(
        tenant_id, user_id, channel, status, limit, offset
    )


@router.post("/notifications/read")
async def mark_as_read(
    notification_ids: list[str],
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> dict:
    """Mark notifications as read."""
    count = await service.mark_as_read(tenant_id, user_id, notification_ids)
    return {"updated": count}


@router.get("/notifications/unread-count")
async def get_unread_count(
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[NotificationService, Depends(get_notification_service)],
) -> dict:
    """Get unread notification count."""
    count = await service.get_unread_count(tenant_id, user_id)
    return {"count": count}


# Preference endpoints

@router.get("/preferences", response_model=PreferenceResponse)
async def get_preferences(
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[PreferenceService, Depends(get_preference_service)],
) -> PreferenceResponse:
    """Get user notification preferences."""
    prefs = await service.get_preferences(tenant_id, user_id)
    if not prefs:
        # Create default preferences
        prefs = await service.create_preferences(tenant_id, user_id)
    return prefs


@router.patch("/preferences", response_model=PreferenceResponse)
async def update_preferences(
    updates: PreferenceUpdate,
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[PreferenceService, Depends(get_preference_service)],
) -> PreferenceResponse:
    """Update user notification preferences."""
    prefs = await service.update_preferences(tenant_id, user_id, updates)
    if not prefs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preferences not found",
        )
    return prefs


@router.post("/preferences/push-token")
async def register_push_token(
    token: str,
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[PreferenceService, Depends(get_preference_service)],
    device_type: str = "unknown",
) -> dict:
    """Register a push notification token."""
    success = await service.register_push_token(tenant_id, user_id, token, device_type)
    return {"registered": success}


@router.delete("/preferences/push-token")
async def unregister_push_token(
    token: str,
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[PreferenceService, Depends(get_preference_service)],
) -> dict:
    """Unregister a push notification token."""
    success = await service.unregister_push_token(tenant_id, user_id, token)
    return {"unregistered": success}
