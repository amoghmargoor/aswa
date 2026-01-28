import hmac
import hashlib
from typing import Any
from pydantic import BaseModel
import structlog

from aswa_integrations.jira.sync_manager import JiraSyncManager, SyncConfig

logger = structlog.get_logger()


class JiraWebhookEvent(BaseModel):
    """Jira webhook event."""
    timestamp: int
    webhookEvent: str
    issue_event_type_name: str | None = None
    issue: dict | None = None
    comment: dict | None = None
    changelog: dict | None = None
    user: dict | None = None


class JiraWebhookHandler:
    """Handles incoming Jira webhooks."""

    def __init__(
        self,
        sync_manager: JiraSyncManager,
        webhook_secret: str | None = None,
    ):
        """Initialize webhook handler.

        Args:
            sync_manager: Sync manager instance
            webhook_secret: Optional webhook secret for validation
        """
        self.sync_manager = sync_manager
        self.webhook_secret = webhook_secret

    def validate_signature(
        self,
        payload: bytes,
        signature: str,
    ) -> bool:
        """Validate webhook signature.

        Args:
            payload: Raw request body
            signature: Signature from header

        Returns:
            True if valid
        """
        if not self.webhook_secret:
            return True  # No validation if secret not configured

        expected = hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(signature, expected)

    async def handle_webhook(
        self,
        tenant_id: str,
        event: JiraWebhookEvent,
    ) -> dict[str, Any]:
        """Handle a Jira webhook event.

        Args:
            tenant_id: ASWA tenant ID
            event: Webhook event

        Returns:
            Handling result
        """
        logger.info(
            "Jira webhook received",
            event_type=event.webhookEvent,
            issue_key=event.issue.get("key") if event.issue else None,
        )

        handlers = {
            "jira:issue_updated": self._handle_issue_updated,
            "jira:issue_deleted": self._handle_issue_deleted,
            "comment_created": self._handle_comment_created,
            "comment_updated": self._handle_comment_updated,
        }

        handler = handlers.get(event.webhookEvent)
        if not handler:
            logger.debug("Unhandled webhook event", event_type=event.webhookEvent)
            return {"status": "ignored", "reason": "unhandled_event_type"}

        return await handler(tenant_id, event)

    async def _handle_issue_updated(
        self,
        tenant_id: str,
        event: JiraWebhookEvent,
    ) -> dict[str, Any]:
        """Handle issue updated event.

        Args:
            tenant_id: Tenant ID
            event: Webhook event

        Returns:
            Result
        """
        if not event.issue:
            return {"status": "error", "reason": "no_issue_data"}

        issue_key = event.issue["key"]

        # Check if this is a linked issue
        config = SyncConfig()

        try:
            result = await self.sync_manager.sync_issue(
                tenant_id=tenant_id,
                issue_key=issue_key,
                config=config,
            )

            return {
                "status": "synced",
                "sync_status": result.status.value,
                "changes": result.changes,
            }

        except ValueError as e:
            # Issue not linked
            logger.debug("Issue not linked", issue_key=issue_key)
            return {"status": "ignored", "reason": "not_linked"}

        except Exception as e:
            logger.error("Sync failed", issue_key=issue_key, error=str(e))
            return {"status": "error", "reason": str(e)}

    async def _handle_issue_deleted(
        self,
        tenant_id: str,
        event: JiraWebhookEvent,
    ) -> dict[str, Any]:
        """Handle issue deleted event.

        Args:
            tenant_id: Tenant ID
            event: Webhook event

        Returns:
            Result
        """
        if not event.issue:
            return {"status": "error", "reason": "no_issue_data"}

        issue_key = event.issue["key"]

        # Mark link as deleted/orphaned
        # This is handled by the sync manager

        logger.info("Jira issue deleted", issue_key=issue_key)

        return {"status": "acknowledged", "issue_key": issue_key}

    async def _handle_comment_created(
        self,
        tenant_id: str,
        event: JiraWebhookEvent,
    ) -> dict[str, Any]:
        """Handle comment created event.

        Args:
            tenant_id: Tenant ID
            event: Webhook event

        Returns:
            Result
        """
        if not event.issue or not event.comment:
            return {"status": "error", "reason": "missing_data"}

        issue_key = event.issue["key"]
        comment_body = event.comment.get("body", "")
        author = event.comment.get("author", {}).get("displayName", "Unknown")

        logger.info(
            "Jira comment created",
            issue_key=issue_key,
            author=author,
        )

        # Optionally sync comment to ASWA as a note
        # This would be implemented based on requirements

        return {
            "status": "acknowledged",
            "issue_key": issue_key,
            "comment_id": event.comment.get("id"),
        }

    async def _handle_comment_updated(
        self,
        tenant_id: str,
        event: JiraWebhookEvent,
    ) -> dict[str, Any]:
        """Handle comment updated event.

        Args:
            tenant_id: Tenant ID
            event: Webhook event

        Returns:
            Result
        """
        # Similar to comment created
        return await self._handle_comment_created(tenant_id, event)
