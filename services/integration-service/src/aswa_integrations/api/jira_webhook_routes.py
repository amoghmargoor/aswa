from fastapi import APIRouter, Depends, HTTPException, status, Request
from typing import Annotated
import structlog

from aswa_integrations.jira.webhook_handler import JiraWebhookHandler, JiraWebhookEvent
from aswa_integrations.api.dependencies import get_tenant_id

logger = structlog.get_logger()
router = APIRouter(prefix="/jira/webhooks", tags=["jira-webhooks"])

_webhook_handler: JiraWebhookHandler | None = None


def set_webhook_handler(handler: JiraWebhookHandler) -> None:
    """Set the global webhook handler instance."""
    global _webhook_handler
    _webhook_handler = handler


def get_webhook_handler() -> JiraWebhookHandler:
    """Get the webhook handler dependency."""
    if not _webhook_handler:
        raise RuntimeError("Webhook handler not initialized")
    return _webhook_handler


@router.post("/{tenant_id}")
async def handle_jira_webhook(
    tenant_id: str,
    request: Request,
    handler: Annotated[JiraWebhookHandler, Depends(get_webhook_handler)],
) -> dict:
    """Handle incoming Jira webhook."""
    # Get raw body for signature validation
    body = await request.body()

    # Validate signature if configured
    signature = request.headers.get("X-Hub-Signature")
    if signature and not handler.validate_signature(body, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    # Parse event
    try:
        event_data = await request.json()
        event = JiraWebhookEvent(**event_data)
    except Exception as e:
        logger.error("Invalid webhook payload", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook payload",
        )

    # Handle event
    result = await handler.handle_webhook(tenant_id, event)

    return result
