from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import Annotated
import structlog

from aswa_integrations.models.webhook import (
    WebhookCreate,
    WebhookUpdate,
    WebhookResponse,
    WebhookDeliveryResponse,
    WebhookEvent,
    WebhookEventType,
)
from aswa_integrations.services.webhook_manager import WebhookManager
from aswa_integrations.api.dependencies import get_tenant_id

logger = structlog.get_logger()
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_webhook_manager: WebhookManager | None = None


def set_webhook_manager(manager: WebhookManager) -> None:
    """Set the global webhook manager instance."""
    global _webhook_manager
    _webhook_manager = manager


def get_webhook_manager() -> WebhookManager:
    """Get the webhook manager dependency."""
    if not _webhook_manager:
        raise RuntimeError("Webhook manager not initialized")
    return _webhook_manager


@router.post("", response_model=WebhookResponse, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    data: WebhookCreate,
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    manager: Annotated[WebhookManager, Depends(get_webhook_manager)],
) -> WebhookResponse:
    """Create a new webhook."""
    return await manager.create_webhook(tenant_id, data)


@router.get("", response_model=list[WebhookResponse])
async def list_webhooks(
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    manager: Annotated[WebhookManager, Depends(get_webhook_manager)],
    event_type: WebhookEventType | None = None,
    is_active: bool | None = None,
) -> list[WebhookResponse]:
    """List all webhooks for a tenant."""
    return await manager.list_webhooks(tenant_id, event_type, is_active)


@router.get("/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(
    webhook_id: str,
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    manager: Annotated[WebhookManager, Depends(get_webhook_manager)],
) -> WebhookResponse:
    """Get a webhook by ID."""
    webhook = await manager.get_webhook(tenant_id, webhook_id)
    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found",
        )
    return webhook


@router.patch("/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(
    webhook_id: str,
    data: WebhookUpdate,
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    manager: Annotated[WebhookManager, Depends(get_webhook_manager)],
) -> WebhookResponse:
    """Update a webhook."""
    webhook = await manager.update_webhook(tenant_id, webhook_id, data)
    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found",
        )
    return webhook


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    webhook_id: str,
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    manager: Annotated[WebhookManager, Depends(get_webhook_manager)],
) -> None:
    """Delete a webhook."""
    deleted = await manager.delete_webhook(tenant_id, webhook_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found",
        )


@router.get("/{webhook_id}/deliveries", response_model=list[WebhookDeliveryResponse])
async def get_delivery_history(
    webhook_id: str,
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    manager: Annotated[WebhookManager, Depends(get_webhook_manager)],
    limit: int = 50,
) -> list[WebhookDeliveryResponse]:
    """Get delivery history for a webhook."""
    return await manager.get_delivery_history(tenant_id, webhook_id, limit)


@router.post("/{webhook_id}/test")
async def test_webhook(
    webhook_id: str,
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    manager: Annotated[WebhookManager, Depends(get_webhook_manager)],
    background_tasks: BackgroundTasks,
) -> dict:
    """Send a test event to a webhook."""
    webhook = await manager.get_webhook(tenant_id, webhook_id)
    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found",
        )

    # Create test event
    test_event = WebhookEvent(
        type=WebhookEventType.INSIGHT_CREATED,
        tenant_id=tenant_id,
        data={
            "test": True,
            "message": "This is a test webhook event from ASWA",
        },
    )

    # Dispatch in background
    background_tasks.add_task(manager.dispatch_event, test_event)

    return {"status": "test_dispatched", "event_id": test_event.id}


# Internal endpoint for dispatching events
@router.post("/dispatch", include_in_schema=False)
async def dispatch_event(
    event: WebhookEvent,
    manager: Annotated[WebhookManager, Depends(get_webhook_manager)],
) -> dict:
    """Dispatch an event to all matching webhooks (internal use)."""
    delivery_ids = await manager.dispatch_event(event)
    return {"delivery_ids": delivery_ids}
