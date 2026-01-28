# Task 6.2.3: Jira Integration - Bi-directional Sync

## Context

You are working on the ASWA integration service at `/services/integration-service/`. Issue creation is complete (Task 6.2.2). Now we need to implement bi-directional synchronization between Jira and ASWA.

## Objective

Create bi-directional sync that:
1. Syncs Jira issue updates back to ASWA
2. Handles Jira webhooks for real-time updates
3. Polls for changes when webhooks unavailable
4. Manages conflict resolution
5. Provides sync status visibility

## Requirements

### 1. Create `/services/integration-service/src/aswa_integrations/jira/sync_manager.py`
```python
import asyncio
from datetime import datetime, timedelta
from enum import Enum
from typing import Any
import httpx
from sqlalchemy import Column, String, DateTime, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import select, update
import uuid
from pydantic import BaseModel
import structlog

from aswa_integrations.models.integration import Base
from aswa_integrations.jira.oauth import JiraOAuthHandler
from aswa_integrations.jira.issue_manager import JiraIssueManager, JiraIssueLinkDB

logger = structlog.get_logger()


class SyncDirection(str, Enum):
    """Sync direction."""
    ASWA_TO_JIRA = "aswa_to_jira"
    JIRA_TO_ASWA = "jira_to_aswa"
    BIDIRECTIONAL = "bidirectional"


class SyncStatus(str, Enum):
    """Sync status."""
    SYNCED = "synced"
    PENDING = "pending"
    CONFLICT = "conflict"
    ERROR = "error"


class JiraSyncLogDB(Base):
    """Database model for sync history."""

    __tablename__ = "jira_sync_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, nullable=False, index=True)
    link_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    direction = Column(String, nullable=False)
    status = Column(String, nullable=False)
    changes = Column(JSON, default={})
    error = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SyncConfig(BaseModel):
    """Sync configuration."""
    sync_interval_seconds: int = 300  # 5 minutes
    sync_status_changes: bool = True
    sync_comments: bool = True
    sync_priority: bool = True
    sync_assignee: bool = False
    conflict_resolution: str = "jira_wins"  # or "aswa_wins", "newest_wins"


class JiraSyncResult(BaseModel):
    """Sync operation result."""
    link_id: str
    insight_id: str
    issue_key: str
    direction: SyncDirection
    status: SyncStatus
    changes: dict[str, Any] = {}
    error: str | None = None
    synced_at: datetime


class JiraSyncManager:
    """Manages bi-directional sync between ASWA and Jira."""

    API_BASE = "https://api.atlassian.com/ex/jira"

    def __init__(
        self,
        oauth_handler: JiraOAuthHandler,
        issue_manager: JiraIssueManager,
        session_factory,
        api_gateway_url: str,
    ):
        """Initialize sync manager.

        Args:
            oauth_handler: OAuth handler
            issue_manager: Issue manager
            session_factory: Database session factory
            api_gateway_url: ASWA API gateway URL
        """
        self.oauth_handler = oauth_handler
        self.issue_manager = issue_manager
        self.session_factory = session_factory
        self.api_gateway_url = api_gateway_url
        self._sync_task: asyncio.Task | None = None

    async def start_background_sync(
        self,
        config: SyncConfig,
    ) -> None:
        """Start background sync task.

        Args:
            config: Sync configuration
        """
        if self._sync_task and not self._sync_task.done():
            return

        self._sync_task = asyncio.create_task(
            self._sync_loop(config)
        )
        logger.info("Background sync started", interval=config.sync_interval_seconds)

    async def stop_background_sync(self) -> None:
        """Stop background sync task."""
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
            self._sync_task = None
            logger.info("Background sync stopped")

    async def _sync_loop(
        self,
        config: SyncConfig,
    ) -> None:
        """Background sync loop.

        Args:
            config: Sync configuration
        """
        while True:
            try:
                await self.sync_all_tenants(config)
            except Exception as e:
                logger.error("Sync loop error", error=str(e))

            await asyncio.sleep(config.sync_interval_seconds)

    async def sync_all_tenants(
        self,
        config: SyncConfig,
    ) -> list[JiraSyncResult]:
        """Sync all tenants.

        Args:
            config: Sync configuration

        Returns:
            List of sync results
        """
        # Get all links that need syncing
        async with self.session_factory() as session:
            result = await session.execute(
                select(JiraIssueLinkDB).where(
                    JiraIssueLinkDB.last_synced_at < datetime.utcnow() - timedelta(seconds=config.sync_interval_seconds)
                )
            )
            links = result.scalars().all()

        results = []
        for link in links:
            try:
                sync_result = await self.sync_issue(
                    tenant_id=link.tenant_id,
                    issue_key=link.jira_issue_key,
                    config=config,
                )
                results.append(sync_result)
            except Exception as e:
                logger.error(
                    "Issue sync failed",
                    issue_key=link.jira_issue_key,
                    error=str(e),
                )

        return results

    async def sync_issue(
        self,
        tenant_id: str,
        issue_key: str,
        config: SyncConfig,
    ) -> JiraSyncResult:
        """Sync a single issue.

        Args:
            tenant_id: ASWA tenant ID
            issue_key: Jira issue key
            config: Sync configuration

        Returns:
            Sync result
        """
        # Get link
        async with self.session_factory() as session:
            result = await session.execute(
                select(JiraIssueLinkDB).where(
                    JiraIssueLinkDB.tenant_id == tenant_id,
                    JiraIssueLinkDB.jira_issue_key == issue_key,
                )
            )
            link = result.scalar_one_or_none()

        if not link:
            raise ValueError(f"No link found for issue {issue_key}")

        # Get current Jira issue state
        jira_issue = await self.issue_manager.get_issue(tenant_id, issue_key)
        if not jira_issue:
            return JiraSyncResult(
                link_id=str(link.id),
                insight_id=link.insight_id,
                issue_key=issue_key,
                direction=SyncDirection.JIRA_TO_ASWA,
                status=SyncStatus.ERROR,
                error="Issue not found in Jira",
                synced_at=datetime.utcnow(),
            )

        # Get current ASWA insight state
        insight = await self._get_insight(tenant_id, link.insight_id)
        if not insight:
            return JiraSyncResult(
                link_id=str(link.id),
                insight_id=link.insight_id,
                issue_key=issue_key,
                direction=SyncDirection.ASWA_TO_JIRA,
                status=SyncStatus.ERROR,
                error="Insight not found in ASWA",
                synced_at=datetime.utcnow(),
            )

        # Detect changes
        changes = self._detect_changes(
            jira_issue=jira_issue,
            insight=insight,
            last_sync_metadata=link.sync_metadata or {},
            config=config,
        )

        if not changes["jira_changes"] and not changes["aswa_changes"]:
            # No changes
            await self._update_link_sync_time(link.id)
            return JiraSyncResult(
                link_id=str(link.id),
                insight_id=link.insight_id,
                issue_key=issue_key,
                direction=SyncDirection.BIDIRECTIONAL,
                status=SyncStatus.SYNCED,
                synced_at=datetime.utcnow(),
            )

        # Handle conflicts
        if changes["jira_changes"] and changes["aswa_changes"]:
            return await self._resolve_conflict(
                link=link,
                jira_issue=jira_issue,
                insight=insight,
                changes=changes,
                config=config,
            )

        # Apply changes
        if changes["jira_changes"]:
            # Jira changed, sync to ASWA
            return await self._sync_jira_to_aswa(
                link=link,
                jira_issue=jira_issue,
                changes=changes["jira_changes"],
                config=config,
            )
        else:
            # ASWA changed, sync to Jira
            return await self._sync_aswa_to_jira(
                tenant_id=tenant_id,
                link=link,
                insight=insight,
                changes=changes["aswa_changes"],
                config=config,
            )

    def _detect_changes(
        self,
        jira_issue,
        insight: dict,
        last_sync_metadata: dict,
        config: SyncConfig,
    ) -> dict[str, dict]:
        """Detect changes between Jira and ASWA.

        Args:
            jira_issue: Current Jira issue
            insight: Current ASWA insight
            last_sync_metadata: Metadata from last sync
            config: Sync configuration

        Returns:
            Dictionary with jira_changes and aswa_changes
        """
        jira_changes = {}
        aswa_changes = {}

        # Check status
        if config.sync_status_changes:
            last_jira_status = last_sync_metadata.get("jira_status")
            last_aswa_status = last_sync_metadata.get("aswa_status")

            if jira_issue.status != last_jira_status:
                jira_changes["status"] = jira_issue.status

            insight_status = insight.get("status")
            if insight_status != last_aswa_status:
                aswa_changes["status"] = insight_status

        # Check priority
        if config.sync_priority:
            last_jira_priority = last_sync_metadata.get("jira_priority")
            last_aswa_severity = last_sync_metadata.get("aswa_severity")

            if jira_issue.priority != last_jira_priority:
                jira_changes["priority"] = jira_issue.priority

            insight_severity = insight.get("severity")
            if insight_severity != last_aswa_severity:
                aswa_changes["severity"] = insight_severity

        return {
            "jira_changes": jira_changes,
            "aswa_changes": aswa_changes,
        }

    async def _resolve_conflict(
        self,
        link: JiraIssueLinkDB,
        jira_issue,
        insight: dict,
        changes: dict,
        config: SyncConfig,
    ) -> JiraSyncResult:
        """Resolve sync conflict.

        Args:
            link: Issue link
            jira_issue: Jira issue
            insight: ASWA insight
            changes: Detected changes
            config: Sync configuration

        Returns:
            Sync result
        """
        if config.conflict_resolution == "jira_wins":
            return await self._sync_jira_to_aswa(
                link=link,
                jira_issue=jira_issue,
                changes=changes["jira_changes"],
                config=config,
            )
        elif config.conflict_resolution == "aswa_wins":
            return await self._sync_aswa_to_jira(
                tenant_id=link.tenant_id,
                link=link,
                insight=insight,
                changes=changes["aswa_changes"],
                config=config,
            )
        elif config.conflict_resolution == "newest_wins":
            jira_updated = jira_issue.updated
            aswa_updated = datetime.fromisoformat(insight.get("updated_at", "2000-01-01"))

            if jira_updated > aswa_updated:
                return await self._sync_jira_to_aswa(
                    link=link,
                    jira_issue=jira_issue,
                    changes=changes["jira_changes"],
                    config=config,
                )
            else:
                return await self._sync_aswa_to_jira(
                    tenant_id=link.tenant_id,
                    link=link,
                    insight=insight,
                    changes=changes["aswa_changes"],
                    config=config,
                )
        else:
            # Mark as conflict for manual resolution
            return JiraSyncResult(
                link_id=str(link.id),
                insight_id=link.insight_id,
                issue_key=link.jira_issue_key,
                direction=SyncDirection.BIDIRECTIONAL,
                status=SyncStatus.CONFLICT,
                changes=changes,
                synced_at=datetime.utcnow(),
            )

    async def _sync_jira_to_aswa(
        self,
        link: JiraIssueLinkDB,
        jira_issue,
        changes: dict,
        config: SyncConfig,
    ) -> JiraSyncResult:
        """Sync Jira changes to ASWA.

        Args:
            link: Issue link
            jira_issue: Jira issue
            changes: Changes to sync
            config: Sync configuration

        Returns:
            Sync result
        """
        try:
            # Map Jira status to ASWA status
            if "status" in changes:
                aswa_status = self._map_jira_status_to_aswa(changes["status"])
                await self._update_insight_status(
                    link.tenant_id,
                    link.insight_id,
                    aswa_status,
                )

            # Update sync metadata
            await self._update_sync_metadata(
                link_id=link.id,
                metadata={
                    "jira_status": jira_issue.status,
                    "jira_priority": jira_issue.priority,
                    "last_sync_direction": "jira_to_aswa",
                },
            )

            # Log sync
            await self._log_sync(
                tenant_id=link.tenant_id,
                link_id=link.id,
                direction=SyncDirection.JIRA_TO_ASWA,
                status=SyncStatus.SYNCED,
                changes=changes,
            )

            return JiraSyncResult(
                link_id=str(link.id),
                insight_id=link.insight_id,
                issue_key=link.jira_issue_key,
                direction=SyncDirection.JIRA_TO_ASWA,
                status=SyncStatus.SYNCED,
                changes=changes,
                synced_at=datetime.utcnow(),
            )

        except Exception as e:
            await self._log_sync(
                tenant_id=link.tenant_id,
                link_id=link.id,
                direction=SyncDirection.JIRA_TO_ASWA,
                status=SyncStatus.ERROR,
                error=str(e),
            )

            return JiraSyncResult(
                link_id=str(link.id),
                insight_id=link.insight_id,
                issue_key=link.jira_issue_key,
                direction=SyncDirection.JIRA_TO_ASWA,
                status=SyncStatus.ERROR,
                error=str(e),
                synced_at=datetime.utcnow(),
            )

    async def _sync_aswa_to_jira(
        self,
        tenant_id: str,
        link: JiraIssueLinkDB,
        insight: dict,
        changes: dict,
        config: SyncConfig,
    ) -> JiraSyncResult:
        """Sync ASWA changes to Jira.

        Args:
            tenant_id: Tenant ID
            link: Issue link
            insight: ASWA insight
            changes: Changes to sync
            config: Sync configuration

        Returns:
            Sync result
        """
        try:
            jira_updates = {}

            # Map ASWA status to Jira transition
            if "status" in changes:
                transition_name = self._map_aswa_status_to_jira(changes["status"])
                if transition_name:
                    await self.issue_manager.transition_issue(
                        tenant_id,
                        link.jira_issue_key,
                        transition_name,
                    )

            # Map severity to priority
            if "severity" in changes:
                priority = self._map_severity_to_priority(changes["severity"])
                jira_updates["priority"] = priority

            # Apply other updates
            if jira_updates:
                await self.issue_manager.update_issue(
                    tenant_id,
                    link.jira_issue_key,
                    jira_updates,
                )

            # Update sync metadata
            await self._update_sync_metadata(
                link_id=link.id,
                metadata={
                    "aswa_status": insight.get("status"),
                    "aswa_severity": insight.get("severity"),
                    "last_sync_direction": "aswa_to_jira",
                },
            )

            await self._log_sync(
                tenant_id=tenant_id,
                link_id=link.id,
                direction=SyncDirection.ASWA_TO_JIRA,
                status=SyncStatus.SYNCED,
                changes=changes,
            )

            return JiraSyncResult(
                link_id=str(link.id),
                insight_id=link.insight_id,
                issue_key=link.jira_issue_key,
                direction=SyncDirection.ASWA_TO_JIRA,
                status=SyncStatus.SYNCED,
                changes=changes,
                synced_at=datetime.utcnow(),
            )

        except Exception as e:
            await self._log_sync(
                tenant_id=tenant_id,
                link_id=link.id,
                direction=SyncDirection.ASWA_TO_JIRA,
                status=SyncStatus.ERROR,
                error=str(e),
            )

            return JiraSyncResult(
                link_id=str(link.id),
                insight_id=link.insight_id,
                issue_key=link.jira_issue_key,
                direction=SyncDirection.ASWA_TO_JIRA,
                status=SyncStatus.ERROR,
                error=str(e),
                synced_at=datetime.utcnow(),
            )

    def _map_jira_status_to_aswa(self, jira_status: str) -> str:
        """Map Jira status to ASWA status."""
        mapping = {
            "To Do": "new",
            "Open": "new",
            "Backlog": "new",
            "In Progress": "in_progress",
            "In Development": "in_progress",
            "In Review": "in_progress",
            "Done": "resolved",
            "Closed": "resolved",
            "Resolved": "resolved",
            "Won't Do": "dismissed",
            "Rejected": "dismissed",
        }
        return mapping.get(jira_status, "new")

    def _map_aswa_status_to_jira(self, aswa_status: str) -> str | None:
        """Map ASWA status to Jira transition name."""
        mapping = {
            "new": "To Do",
            "in_progress": "In Progress",
            "resolved": "Done",
            "dismissed": "Won't Do",
        }
        return mapping.get(aswa_status)

    def _map_severity_to_priority(self, severity: str) -> str:
        """Map ASWA severity to Jira priority."""
        mapping = {
            "critical": "Highest",
            "high": "High",
            "medium": "Medium",
            "low": "Low",
        }
        return mapping.get(severity, "Medium")

    async def _get_insight(
        self,
        tenant_id: str,
        insight_id: str,
    ) -> dict | None:
        """Get insight from ASWA API."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_gateway_url}/api/v1/insights/{insight_id}",
                headers={"X-Tenant-ID": tenant_id},
            )
            if response.is_success:
                return response.json()
            return None

    async def _update_insight_status(
        self,
        tenant_id: str,
        insight_id: str,
        status: str,
    ) -> None:
        """Update insight status in ASWA."""
        async with httpx.AsyncClient() as client:
            await client.patch(
                f"{self.api_gateway_url}/api/v1/insights/{insight_id}",
                headers={"X-Tenant-ID": tenant_id},
                json={"status": status},
            )

    async def _update_link_sync_time(self, link_id) -> None:
        """Update link sync timestamp."""
        async with self.session_factory() as session:
            await session.execute(
                update(JiraIssueLinkDB)
                .where(JiraIssueLinkDB.id == link_id)
                .values(last_synced_at=datetime.utcnow())
            )
            await session.commit()

    async def _update_sync_metadata(
        self,
        link_id,
        metadata: dict,
    ) -> None:
        """Update link sync metadata."""
        async with self.session_factory() as session:
            await session.execute(
                update(JiraIssueLinkDB)
                .where(JiraIssueLinkDB.id == link_id)
                .values(
                    sync_metadata=metadata,
                    last_synced_at=datetime.utcnow(),
                )
            )
            await session.commit()

    async def _log_sync(
        self,
        tenant_id: str,
        link_id,
        direction: SyncDirection,
        status: SyncStatus,
        changes: dict | None = None,
        error: str | None = None,
    ) -> None:
        """Log sync operation."""
        log = JiraSyncLogDB(
            tenant_id=tenant_id,
            link_id=link_id,
            direction=direction.value,
            status=status.value,
            changes=changes or {},
            error=error,
        )

        async with self.session_factory() as session:
            session.add(log)
            await session.commit()
```

### 2. Create `/services/integration-service/src/aswa_integrations/jira/webhook_handler.py`
```python
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
```

### 3. Create `/services/integration-service/src/aswa_integrations/api/jira_webhook_routes.py`
```python
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
```

## Test Requirements

### Create `/services/integration-service/tests/jira/test_sync_manager.py`
```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from aswa_integrations.jira.sync_manager import (
    JiraSyncManager,
    SyncConfig,
    SyncDirection,
    SyncStatus,
)


class TestJiraSyncManager:
    @pytest.fixture
    def sync_config(self):
        return SyncConfig(
            sync_interval_seconds=300,
            sync_status_changes=True,
            sync_comments=True,
            conflict_resolution="jira_wins",
        )

    def test_map_jira_status_to_aswa(self):
        """Test Jira to ASWA status mapping."""
        manager = JiraSyncManager(
            MagicMock(), MagicMock(), MagicMock(), "http://localhost"
        )

        assert manager._map_jira_status_to_aswa("To Do") == "new"
        assert manager._map_jira_status_to_aswa("In Progress") == "in_progress"
        assert manager._map_jira_status_to_aswa("Done") == "resolved"
        assert manager._map_jira_status_to_aswa("Won't Do") == "dismissed"

    def test_map_aswa_status_to_jira(self):
        """Test ASWA to Jira status mapping."""
        manager = JiraSyncManager(
            MagicMock(), MagicMock(), MagicMock(), "http://localhost"
        )

        assert manager._map_aswa_status_to_jira("new") == "To Do"
        assert manager._map_aswa_status_to_jira("in_progress") == "In Progress"
        assert manager._map_aswa_status_to_jira("resolved") == "Done"

    def test_detect_no_changes(self, sync_config):
        """Test detecting no changes."""
        manager = JiraSyncManager(
            MagicMock(), MagicMock(), MagicMock(), "http://localhost"
        )

        jira_issue = MagicMock()
        jira_issue.status = "In Progress"
        jira_issue.priority = "High"

        insight = {"status": "in_progress", "severity": "high"}

        last_sync = {
            "jira_status": "In Progress",
            "jira_priority": "High",
            "aswa_status": "in_progress",
            "aswa_severity": "high",
        }

        changes = manager._detect_changes(
            jira_issue, insight, last_sync, sync_config
        )

        assert not changes["jira_changes"]
        assert not changes["aswa_changes"]

    def test_detect_jira_changes(self, sync_config):
        """Test detecting Jira changes."""
        manager = JiraSyncManager(
            MagicMock(), MagicMock(), MagicMock(), "http://localhost"
        )

        jira_issue = MagicMock()
        jira_issue.status = "Done"  # Changed
        jira_issue.priority = "High"

        insight = {"status": "in_progress", "severity": "high"}

        last_sync = {
            "jira_status": "In Progress",
            "jira_priority": "High",
            "aswa_status": "in_progress",
            "aswa_severity": "high",
        }

        changes = manager._detect_changes(
            jira_issue, insight, last_sync, sync_config
        )

        assert "status" in changes["jira_changes"]
        assert changes["jira_changes"]["status"] == "Done"
        assert not changes["aswa_changes"]


class TestJiraWebhookHandler:
    @pytest.mark.asyncio
    async def test_handle_issue_updated(self):
        """Test handling issue updated webhook."""
        from aswa_integrations.jira.webhook_handler import (
            JiraWebhookHandler,
            JiraWebhookEvent,
        )

        sync_manager = MagicMock()
        sync_manager.sync_issue = AsyncMock(return_value=MagicMock(
            status=SyncStatus.SYNCED,
            changes={"status": "Done"},
        ))

        handler = JiraWebhookHandler(sync_manager)

        event = JiraWebhookEvent(
            timestamp=1234567890,
            webhookEvent="jira:issue_updated",
            issue={"key": "TEST-123"},
        )

        result = await handler.handle_webhook("tenant-123", event)

        assert result["status"] == "synced"
        sync_manager.sync_issue.assert_called_once()
```

## Verification

1. Run tests: `pytest tests/jira/test_sync_manager.py -v`
2. Test bi-directional sync with sample issues
3. Verify webhook handling
4. Test conflict resolution modes
5. Check sync logs for audit trail
