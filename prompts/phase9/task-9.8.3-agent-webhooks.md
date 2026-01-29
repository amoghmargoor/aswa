# Task 9.8.3: Agent Webhooks

## Objective

Implement webhook functionality for agents that enables real-time notifications and external system integrations when agent events occur.

## Prerequisites

- Task 9.8.1-9.8.2 completed (Triggers and OAuth)
- Agent execution infrastructure
- Event system

## Implementation

### Step 1: Webhook Models

```python
# services/agent-service/src/aswa_agents/webhooks/models.py
"""Webhook models for agent notifications."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import Column, String, DateTime, JSON, Boolean, Integer, Text, Index
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from aswa_agents.db.base import Base


class WebhookEvent(str, Enum):
    """Webhook event types."""

    # Agent lifecycle
    AGENT_CREATED = "agent.created"
    AGENT_UPDATED = "agent.updated"
    AGENT_DELETED = "agent.deleted"
    AGENT_DEPLOYED = "agent.deployed"

    # Execution events
    EXECUTION_STARTED = "execution.started"
    EXECUTION_COMPLETED = "execution.completed"
    EXECUTION_FAILED = "execution.failed"

    # Action events
    ACTION_STARTED = "action.started"
    ACTION_COMPLETED = "action.completed"
    ACTION_FAILED = "action.failed"

    # Approval events
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_APPROVED = "approval.approved"
    APPROVAL_REJECTED = "approval.rejected"

    # All events
    ALL = "*"


class WebhookStatus(str, Enum):
    """Webhook subscription status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    FAILED = "failed"


class WebhookDeliveryStatus(str, Enum):
    """Delivery attempt status."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


class WebhookSubscriptionModel(Base):
    """SQLAlchemy model for webhook subscriptions."""

    __tablename__ = "webhook_subscriptions"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(String(100), nullable=False)

    # Subscription details
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    url = Column(String(500), nullable=False)

    # Scope
    agent_id = Column(PGUUID(as_uuid=True), nullable=True)  # Null = all agents
    events = Column(JSON, default=list)  # List of event types

    # Authentication
    secret = Column(String(200), nullable=True)  # For signature
    headers = Column(JSON, default=dict)  # Custom headers

    # Configuration
    enabled = Column(Boolean, default=True)
    retry_count = Column(Integer, default=3)
    timeout_seconds = Column(Integer, default=30)

    # Status
    status = Column(String(50), default=WebhookStatus.ACTIVE.value)
    last_triggered = Column(DateTime, nullable=True)
    failure_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(100), nullable=True)

    __table_args__ = (
        Index("idx_webhook_subscriptions_tenant", "tenant_id"),
        Index("idx_webhook_subscriptions_agent", "agent_id"),
        Index("idx_webhook_subscriptions_status", "status"),
    )


class WebhookDeliveryModel(Base):
    """SQLAlchemy model for webhook delivery attempts."""

    __tablename__ = "webhook_deliveries"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    subscription_id = Column(PGUUID(as_uuid=True), nullable=False)
    tenant_id = Column(String(100), nullable=False)

    # Event info
    event_type = Column(String(100), nullable=False)
    event_id = Column(String(100), nullable=False)
    payload = Column(JSON, nullable=False)

    # Delivery status
    status = Column(String(50), default=WebhookDeliveryStatus.PENDING.value)
    attempt_count = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)

    # Response
    response_status = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    delivered_at = Column(DateTime, nullable=True)
    next_retry_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_webhook_deliveries_subscription", "subscription_id"),
        Index("idx_webhook_deliveries_status", "status"),
        Index("idx_webhook_deliveries_next_retry", "next_retry_at"),
    )


# Pydantic models
class WebhookSubscriptionCreate(BaseModel):
    """Create webhook subscription request."""

    name: str
    url: HttpUrl
    description: str | None = None
    agent_id: UUID | None = None
    events: list[WebhookEvent] = Field(default_factory=lambda: [WebhookEvent.ALL])
    secret: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    retry_count: int = 3
    timeout_seconds: int = 30


class WebhookSubscriptionUpdate(BaseModel):
    """Update webhook subscription request."""

    name: str | None = None
    url: HttpUrl | None = None
    description: str | None = None
    events: list[WebhookEvent] | None = None
    headers: dict[str, str] | None = None
    enabled: bool | None = None
    retry_count: int | None = None


class WebhookSubscriptionResponse(BaseModel):
    """Webhook subscription response."""

    id: UUID
    name: str
    url: str
    description: str | None
    agent_id: UUID | None
    events: list[str]
    enabled: bool
    status: str
    last_triggered: datetime | None
    failure_count: int
    created_at: datetime


class WebhookDeliveryResponse(BaseModel):
    """Webhook delivery response."""

    id: UUID
    event_type: str
    status: str
    attempt_count: int
    response_status: int | None
    response_time_ms: int | None
    error_message: str | None
    created_at: datetime
    delivered_at: datetime | None


class WebhookPayload(BaseModel):
    """Standard webhook payload."""

    event_id: str
    event_type: str
    timestamp: datetime
    tenant_id: str
    agent_id: str | None = None
    data: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)
```

### Step 2: Webhook Service

```python
# services/agent-service/src/aswa_agents/webhooks/service.py
"""Webhook service for agent notifications."""

import asyncio
import hashlib
import hmac
import json
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import httpx
import structlog

from aswa_agents.webhooks.models import (
    WebhookEvent,
    WebhookStatus,
    WebhookDeliveryStatus,
    WebhookSubscriptionCreate,
    WebhookSubscriptionUpdate,
    WebhookPayload,
)
from aswa_agents.webhooks.repository import WebhookRepository

logger = structlog.get_logger()


class WebhookService:
    """
    Service for managing webhook subscriptions and deliveries.

    Handles subscription management, event dispatching, and retry logic.
    """

    def __init__(self):
        self._repo = WebhookRepository()
        self._logger = logger.bind(component="WebhookService")
        self._delivery_queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the webhook delivery worker."""
        self._worker_task = asyncio.create_task(self._delivery_worker())
        self._logger.info("Webhook service started")

    async def stop(self) -> None:
        """Stop the webhook delivery worker."""
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        self._logger.info("Webhook service stopped")

    async def create_subscription(
        self,
        tenant_id: str,
        subscription: WebhookSubscriptionCreate,
        created_by: str,
    ) -> dict[str, Any]:
        """Create a webhook subscription."""
        db_subscription = await self._repo.create_subscription(
            tenant_id=tenant_id,
            name=subscription.name,
            url=str(subscription.url),
            description=subscription.description,
            agent_id=subscription.agent_id,
            events=[e.value for e in subscription.events],
            secret=subscription.secret,
            headers=subscription.headers,
            retry_count=subscription.retry_count,
            timeout_seconds=subscription.timeout_seconds,
            created_by=created_by,
        )

        self._logger.info(
            "Webhook subscription created",
            subscription_id=str(db_subscription.id),
            url=subscription.url,
        )

        return self._to_response(db_subscription)

    async def update_subscription(
        self,
        subscription_id: UUID,
        tenant_id: str,
        update: WebhookSubscriptionUpdate,
    ) -> dict[str, Any] | None:
        """Update a webhook subscription."""
        updates = update.model_dump(exclude_unset=True)

        if "url" in updates:
            updates["url"] = str(updates["url"])
        if "events" in updates:
            updates["events"] = [e.value for e in updates["events"]]

        db_subscription = await self._repo.update_subscription(
            subscription_id, tenant_id, updates
        )

        if not db_subscription:
            return None

        return self._to_response(db_subscription)

    async def delete_subscription(
        self,
        subscription_id: UUID,
        tenant_id: str,
    ) -> bool:
        """Delete a webhook subscription."""
        return await self._repo.delete_subscription(subscription_id, tenant_id)

    async def get_subscription(
        self,
        subscription_id: UUID,
        tenant_id: str,
    ) -> dict[str, Any] | None:
        """Get a webhook subscription."""
        subscription = await self._repo.get_subscription(subscription_id, tenant_id)

        if not subscription:
            return None

        return self._to_response(subscription)

    async def list_subscriptions(
        self,
        tenant_id: str,
        agent_id: UUID | None = None,
        enabled_only: bool = False,
    ) -> list[dict[str, Any]]:
        """List webhook subscriptions."""
        subscriptions = await self._repo.list_subscriptions(
            tenant_id, agent_id, enabled_only
        )

        return [self._to_response(s) for s in subscriptions]

    async def dispatch_event(
        self,
        tenant_id: str,
        event_type: WebhookEvent,
        data: dict[str, Any],
        agent_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """
        Dispatch an event to all matching subscriptions.

        Returns the number of subscriptions notified.
        """
        # Get matching subscriptions
        subscriptions = await self._repo.get_matching_subscriptions(
            tenant_id=tenant_id,
            event_type=event_type.value,
            agent_id=agent_id,
        )

        if not subscriptions:
            return 0

        # Create payload
        event_id = str(uuid4())
        payload = WebhookPayload(
            event_id=event_id,
            event_type=event_type.value,
            timestamp=datetime.utcnow(),
            tenant_id=tenant_id,
            agent_id=str(agent_id) if agent_id else None,
            data=data,
            metadata=metadata or {},
        )

        # Queue deliveries
        for subscription in subscriptions:
            delivery = await self._repo.create_delivery(
                subscription_id=subscription.id,
                tenant_id=tenant_id,
                event_type=event_type.value,
                event_id=event_id,
                payload=payload.model_dump(mode="json"),
                max_attempts=subscription.retry_count,
            )

            await self._delivery_queue.put(delivery.id)

        self._logger.debug(
            "Event dispatched",
            event_type=event_type.value,
            subscription_count=len(subscriptions),
        )

        return len(subscriptions)

    async def _delivery_worker(self) -> None:
        """Worker that processes webhook deliveries."""
        while True:
            try:
                delivery_id = await asyncio.wait_for(
                    self._delivery_queue.get(),
                    timeout=5.0,
                )

                await self._process_delivery(delivery_id)

            except asyncio.TimeoutError:
                # Check for pending retries
                await self._process_pending_retries()

            except asyncio.CancelledError:
                break

            except Exception as e:
                self._logger.error("Delivery worker error", error=str(e))
                await asyncio.sleep(1)

    async def _process_delivery(self, delivery_id: UUID) -> None:
        """Process a single delivery."""
        delivery = await self._repo.get_delivery(delivery_id)

        if not delivery:
            return

        subscription = await self._repo.get_subscription_by_id(delivery.subscription_id)

        if not subscription or not subscription.enabled:
            await self._repo.update_delivery_status(
                delivery_id,
                WebhookDeliveryStatus.FAILED.value,
                error="Subscription disabled or not found",
            )
            return

        # Attempt delivery
        try:
            response = await self._send_webhook(
                url=subscription.url,
                payload=delivery.payload,
                secret=subscription.secret,
                headers=subscription.headers,
                timeout=subscription.timeout_seconds,
            )

            await self._repo.update_delivery_status(
                delivery_id,
                WebhookDeliveryStatus.SUCCESS.value,
                response_status=response["status"],
                response_body=response["body"][:1000] if response["body"] else None,
                response_time_ms=response["time_ms"],
            )

            # Update subscription
            await self._repo.update_subscription_triggered(
                subscription.id,
                success=True,
            )

        except Exception as e:
            attempt_count = delivery.attempt_count + 1
            error_message = str(e)

            if attempt_count >= delivery.max_attempts:
                # Final failure
                await self._repo.update_delivery_status(
                    delivery_id,
                    WebhookDeliveryStatus.FAILED.value,
                    error=error_message,
                )
                await self._repo.update_subscription_triggered(
                    subscription.id,
                    success=False,
                    error=error_message,
                )
            else:
                # Schedule retry
                next_retry = datetime.utcnow() + timedelta(
                    seconds=self._get_retry_delay(attempt_count)
                )
                await self._repo.update_delivery_for_retry(
                    delivery_id,
                    attempt_count=attempt_count,
                    next_retry_at=next_retry,
                    error=error_message,
                )

    async def _send_webhook(
        self,
        url: str,
        payload: dict[str, Any],
        secret: str | None,
        headers: dict[str, str] | None,
        timeout: int,
    ) -> dict[str, Any]:
        """Send webhook request."""
        body = json.dumps(payload, default=str)

        request_headers = {
            "Content-Type": "application/json",
            "User-Agent": "ASWA-Webhooks/1.0",
            "X-Webhook-Event": payload.get("event_type", ""),
            "X-Webhook-Delivery": payload.get("event_id", ""),
        }

        # Add custom headers
        if headers:
            request_headers.update(headers)

        # Add signature
        if secret:
            signature = hmac.new(
                secret.encode(),
                body.encode(),
                hashlib.sha256,
            ).hexdigest()
            request_headers["X-Webhook-Signature"] = f"sha256={signature}"

        start_time = datetime.utcnow()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                content=body,
                headers=request_headers,
                timeout=timeout,
            )

        elapsed_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        if response.status_code >= 400:
            raise Exception(f"HTTP {response.status_code}: {response.text[:200]}")

        return {
            "status": response.status_code,
            "body": response.text,
            "time_ms": elapsed_ms,
        }

    async def _process_pending_retries(self) -> None:
        """Process any pending retry deliveries."""
        retries = await self._repo.get_pending_retries()

        for delivery in retries:
            await self._delivery_queue.put(delivery.id)

    def _get_retry_delay(self, attempt: int) -> int:
        """Get delay before next retry (exponential backoff)."""
        return min(60 * (2 ** attempt), 3600)  # Max 1 hour

    async def get_deliveries(
        self,
        tenant_id: str,
        subscription_id: UUID | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get webhook deliveries."""
        deliveries = await self._repo.list_deliveries(
            tenant_id=tenant_id,
            subscription_id=subscription_id,
            status=status,
            limit=limit,
        )

        return [
            {
                "id": str(d.id),
                "subscription_id": str(d.subscription_id),
                "event_type": d.event_type,
                "status": d.status,
                "attempt_count": d.attempt_count,
                "response_status": d.response_status,
                "response_time_ms": d.response_time_ms,
                "error_message": d.error_message,
                "created_at": d.created_at.isoformat(),
                "delivered_at": d.delivered_at.isoformat() if d.delivered_at else None,
            }
            for d in deliveries
        ]

    async def retry_delivery(
        self,
        delivery_id: UUID,
        tenant_id: str,
    ) -> bool:
        """Manually retry a failed delivery."""
        delivery = await self._repo.get_delivery(delivery_id)

        if not delivery or delivery.tenant_id != tenant_id:
            return False

        # Reset for retry
        await self._repo.update_delivery_for_retry(
            delivery_id,
            attempt_count=0,
            next_retry_at=datetime.utcnow(),
        )

        await self._delivery_queue.put(delivery_id)

        return True

    async def test_subscription(
        self,
        subscription_id: UUID,
        tenant_id: str,
    ) -> dict[str, Any]:
        """Send a test webhook to verify configuration."""
        subscription = await self._repo.get_subscription(subscription_id, tenant_id)

        if not subscription:
            raise ValueError("Subscription not found")

        test_payload = {
            "event_id": str(uuid4()),
            "event_type": "test",
            "timestamp": datetime.utcnow().isoformat(),
            "tenant_id": tenant_id,
            "data": {"message": "This is a test webhook"},
            "metadata": {"test": True},
        }

        try:
            response = await self._send_webhook(
                url=subscription.url,
                payload=test_payload,
                secret=subscription.secret,
                headers=subscription.headers,
                timeout=subscription.timeout_seconds,
            )

            return {
                "success": True,
                "status_code": response["status"],
                "response_time_ms": response["time_ms"],
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def _to_response(self, subscription) -> dict[str, Any]:
        """Convert subscription to response dict."""
        return {
            "id": str(subscription.id),
            "name": subscription.name,
            "url": subscription.url,
            "description": subscription.description,
            "agent_id": str(subscription.agent_id) if subscription.agent_id else None,
            "events": subscription.events,
            "enabled": subscription.enabled,
            "status": subscription.status,
            "last_triggered": subscription.last_triggered.isoformat() if subscription.last_triggered else None,
            "failure_count": subscription.failure_count,
            "created_at": subscription.created_at.isoformat(),
        }
```

### Step 3: Webhook Repository

```python
# services/agent-service/src/aswa_agents/webhooks/repository.py
"""Repository for webhook data."""

from datetime import datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select, and_, or_, update, delete, desc
from sqlalchemy.ext.asyncio import AsyncSession

from aswa_agents.db.session import get_session
from aswa_agents.webhooks.models import (
    WebhookSubscriptionModel,
    WebhookDeliveryModel,
    WebhookStatus,
    WebhookDeliveryStatus,
    WebhookEvent,
)

logger = structlog.get_logger()


class WebhookRepository:
    """Repository for webhook data management."""

    def __init__(self, session: AsyncSession | None = None):
        self._session = session
        self._logger = logger.bind(component="WebhookRepository")

    async def _get_session(self) -> AsyncSession:
        if self._session:
            return self._session
        return await get_session()

    # Subscriptions

    async def create_subscription(
        self,
        tenant_id: str,
        name: str,
        url: str,
        events: list[str],
        description: str | None = None,
        agent_id: UUID | None = None,
        secret: str | None = None,
        headers: dict | None = None,
        retry_count: int = 3,
        timeout_seconds: int = 30,
        created_by: str | None = None,
    ) -> WebhookSubscriptionModel:
        """Create a webhook subscription."""
        session = await self._get_session()

        subscription = WebhookSubscriptionModel(
            tenant_id=tenant_id,
            name=name,
            url=url,
            description=description,
            agent_id=agent_id,
            events=events,
            secret=secret,
            headers=headers or {},
            retry_count=retry_count,
            timeout_seconds=timeout_seconds,
            created_by=created_by,
        )

        session.add(subscription)
        await session.commit()
        await session.refresh(subscription)

        return subscription

    async def get_subscription(
        self,
        subscription_id: UUID,
        tenant_id: str,
    ) -> WebhookSubscriptionModel | None:
        """Get a subscription by ID."""
        session = await self._get_session()

        result = await session.execute(
            select(WebhookSubscriptionModel).where(
                and_(
                    WebhookSubscriptionModel.id == subscription_id,
                    WebhookSubscriptionModel.tenant_id == tenant_id,
                )
            )
        )

        return result.scalar_one_or_none()

    async def get_subscription_by_id(
        self,
        subscription_id: UUID,
    ) -> WebhookSubscriptionModel | None:
        """Get subscription by ID without tenant check."""
        session = await self._get_session()

        result = await session.execute(
            select(WebhookSubscriptionModel).where(
                WebhookSubscriptionModel.id == subscription_id
            )
        )

        return result.scalar_one_or_none()

    async def list_subscriptions(
        self,
        tenant_id: str,
        agent_id: UUID | None = None,
        enabled_only: bool = False,
    ) -> list[WebhookSubscriptionModel]:
        """List subscriptions."""
        session = await self._get_session()

        conditions = [WebhookSubscriptionModel.tenant_id == tenant_id]

        if agent_id:
            conditions.append(WebhookSubscriptionModel.agent_id == agent_id)

        if enabled_only:
            conditions.append(WebhookSubscriptionModel.enabled == True)

        result = await session.execute(
            select(WebhookSubscriptionModel)
            .where(and_(*conditions))
            .order_by(desc(WebhookSubscriptionModel.created_at))
        )

        return result.scalars().all()

    async def get_matching_subscriptions(
        self,
        tenant_id: str,
        event_type: str,
        agent_id: UUID | None = None,
    ) -> list[WebhookSubscriptionModel]:
        """Get subscriptions matching an event."""
        session = await self._get_session()

        conditions = [
            WebhookSubscriptionModel.tenant_id == tenant_id,
            WebhookSubscriptionModel.enabled == True,
            WebhookSubscriptionModel.status == WebhookStatus.ACTIVE.value,
        ]

        # Filter by agent
        if agent_id:
            conditions.append(
                or_(
                    WebhookSubscriptionModel.agent_id == None,
                    WebhookSubscriptionModel.agent_id == agent_id,
                )
            )

        result = await session.execute(
            select(WebhookSubscriptionModel).where(and_(*conditions))
        )

        subscriptions = result.scalars().all()

        # Filter by event type
        matching = []
        for sub in subscriptions:
            if WebhookEvent.ALL.value in sub.events or event_type in sub.events:
                matching.append(sub)

        return matching

    async def update_subscription(
        self,
        subscription_id: UUID,
        tenant_id: str,
        updates: dict[str, Any],
    ) -> WebhookSubscriptionModel | None:
        """Update a subscription."""
        session = await self._get_session()

        result = await session.execute(
            select(WebhookSubscriptionModel).where(
                and_(
                    WebhookSubscriptionModel.id == subscription_id,
                    WebhookSubscriptionModel.tenant_id == tenant_id,
                )
            )
        )

        subscription = result.scalar_one_or_none()

        if not subscription:
            return None

        for key, value in updates.items():
            if hasattr(subscription, key):
                setattr(subscription, key, value)

        subscription.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(subscription)

        return subscription

    async def update_subscription_triggered(
        self,
        subscription_id: UUID,
        success: bool,
        error: str | None = None,
    ) -> None:
        """Update subscription after trigger."""
        session = await self._get_session()

        values = {
            "last_triggered": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        if success:
            values["failure_count"] = 0
            values["status"] = WebhookStatus.ACTIVE.value
            values["last_error"] = None
        else:
            values["last_error"] = error

        # Get current failure count
        result = await session.execute(
            select(WebhookSubscriptionModel.failure_count).where(
                WebhookSubscriptionModel.id == subscription_id
            )
        )
        current_count = result.scalar() or 0

        if not success:
            values["failure_count"] = current_count + 1
            if values["failure_count"] >= 5:
                values["status"] = WebhookStatus.FAILED.value

        await session.execute(
            update(WebhookSubscriptionModel)
            .where(WebhookSubscriptionModel.id == subscription_id)
            .values(**values)
        )

        await session.commit()

    async def delete_subscription(
        self,
        subscription_id: UUID,
        tenant_id: str,
    ) -> bool:
        """Delete a subscription."""
        session = await self._get_session()

        result = await session.execute(
            delete(WebhookSubscriptionModel).where(
                and_(
                    WebhookSubscriptionModel.id == subscription_id,
                    WebhookSubscriptionModel.tenant_id == tenant_id,
                )
            )
        )

        await session.commit()

        return result.rowcount > 0

    # Deliveries

    async def create_delivery(
        self,
        subscription_id: UUID,
        tenant_id: str,
        event_type: str,
        event_id: str,
        payload: dict[str, Any],
        max_attempts: int = 3,
    ) -> WebhookDeliveryModel:
        """Create a delivery record."""
        session = await self._get_session()

        delivery = WebhookDeliveryModel(
            subscription_id=subscription_id,
            tenant_id=tenant_id,
            event_type=event_type,
            event_id=event_id,
            payload=payload,
            max_attempts=max_attempts,
        )

        session.add(delivery)
        await session.commit()
        await session.refresh(delivery)

        return delivery

    async def get_delivery(
        self,
        delivery_id: UUID,
    ) -> WebhookDeliveryModel | None:
        """Get a delivery by ID."""
        session = await self._get_session()

        result = await session.execute(
            select(WebhookDeliveryModel).where(
                WebhookDeliveryModel.id == delivery_id
            )
        )

        return result.scalar_one_or_none()

    async def list_deliveries(
        self,
        tenant_id: str,
        subscription_id: UUID | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[WebhookDeliveryModel]:
        """List deliveries."""
        session = await self._get_session()

        conditions = [WebhookDeliveryModel.tenant_id == tenant_id]

        if subscription_id:
            conditions.append(WebhookDeliveryModel.subscription_id == subscription_id)

        if status:
            conditions.append(WebhookDeliveryModel.status == status)

        result = await session.execute(
            select(WebhookDeliveryModel)
            .where(and_(*conditions))
            .order_by(desc(WebhookDeliveryModel.created_at))
            .limit(limit)
        )

        return result.scalars().all()

    async def update_delivery_status(
        self,
        delivery_id: UUID,
        status: str,
        response_status: int | None = None,
        response_body: str | None = None,
        response_time_ms: int | None = None,
        error: str | None = None,
    ) -> None:
        """Update delivery status."""
        session = await self._get_session()

        values = {
            "status": status,
            "error_message": error,
        }

        if status == WebhookDeliveryStatus.SUCCESS.value:
            values["delivered_at"] = datetime.utcnow()

        if response_status:
            values["response_status"] = response_status
        if response_body:
            values["response_body"] = response_body
        if response_time_ms:
            values["response_time_ms"] = response_time_ms

        await session.execute(
            update(WebhookDeliveryModel)
            .where(WebhookDeliveryModel.id == delivery_id)
            .values(**values)
        )

        await session.commit()

    async def update_delivery_for_retry(
        self,
        delivery_id: UUID,
        attempt_count: int,
        next_retry_at: datetime | None = None,
        error: str | None = None,
    ) -> None:
        """Update delivery for retry."""
        session = await self._get_session()

        values = {
            "status": WebhookDeliveryStatus.RETRYING.value,
            "attempt_count": attempt_count,
            "next_retry_at": next_retry_at,
            "error_message": error,
        }

        await session.execute(
            update(WebhookDeliveryModel)
            .where(WebhookDeliveryModel.id == delivery_id)
            .values(**values)
        )

        await session.commit()

    async def get_pending_retries(
        self,
        limit: int = 100,
    ) -> list[WebhookDeliveryModel]:
        """Get deliveries ready for retry."""
        session = await self._get_session()

        result = await session.execute(
            select(WebhookDeliveryModel)
            .where(
                and_(
                    WebhookDeliveryModel.status == WebhookDeliveryStatus.RETRYING.value,
                    WebhookDeliveryModel.next_retry_at <= datetime.utcnow(),
                )
            )
            .limit(limit)
        )

        return result.scalars().all()
```

### Step 4: Webhook API Endpoints

```python
# services/agent-service/src/aswa_agents/api/webhooks.py
"""API endpoints for webhooks."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from aswa_agents.webhooks.models import (
    WebhookSubscriptionCreate,
    WebhookSubscriptionUpdate,
    WebhookEvent,
)
from aswa_agents.webhooks.service import WebhookService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("/events")
async def list_events() -> dict[str, Any]:
    """List available webhook events."""
    return {
        "events": [
            {"value": e.value, "name": e.name}
            for e in WebhookEvent
            if e != WebhookEvent.ALL
        ]
    }


@router.post("/subscriptions")
async def create_subscription(
    subscription: WebhookSubscriptionCreate,
) -> dict[str, Any]:
    """Create a webhook subscription."""
    tenant_id = "default-tenant"
    user_id = "current-user"

    service = WebhookService()

    try:
        return await service.create_subscription(tenant_id, subscription, user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/subscriptions")
async def list_subscriptions(
    agent_id: UUID | None = None,
    enabled_only: bool = False,
) -> dict[str, Any]:
    """List webhook subscriptions."""
    tenant_id = "default-tenant"

    service = WebhookService()
    subscriptions = await service.list_subscriptions(
        tenant_id, agent_id, enabled_only
    )

    return {"subscriptions": subscriptions}


@router.get("/subscriptions/{subscription_id}")
async def get_subscription(subscription_id: UUID) -> dict[str, Any]:
    """Get a webhook subscription."""
    tenant_id = "default-tenant"

    service = WebhookService()
    subscription = await service.get_subscription(subscription_id, tenant_id)

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    return subscription


@router.put("/subscriptions/{subscription_id}")
async def update_subscription(
    subscription_id: UUID,
    update: WebhookSubscriptionUpdate,
) -> dict[str, Any]:
    """Update a webhook subscription."""
    tenant_id = "default-tenant"

    service = WebhookService()
    subscription = await service.update_subscription(
        subscription_id, tenant_id, update
    )

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    return subscription


@router.delete("/subscriptions/{subscription_id}")
async def delete_subscription(subscription_id: UUID) -> dict[str, Any]:
    """Delete a webhook subscription."""
    tenant_id = "default-tenant"

    service = WebhookService()
    success = await service.delete_subscription(subscription_id, tenant_id)

    if not success:
        raise HTTPException(status_code=404, detail="Subscription not found")

    return {"deleted": True}


@router.post("/subscriptions/{subscription_id}/test")
async def test_subscription(subscription_id: UUID) -> dict[str, Any]:
    """Send a test webhook."""
    tenant_id = "default-tenant"

    service = WebhookService()

    try:
        return await service.test_subscription(subscription_id, tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/deliveries")
async def list_deliveries(
    subscription_id: UUID | None = None,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """List webhook deliveries."""
    tenant_id = "default-tenant"

    service = WebhookService()
    deliveries = await service.get_deliveries(
        tenant_id, subscription_id, status, limit
    )

    return {"deliveries": deliveries}


@router.post("/deliveries/{delivery_id}/retry")
async def retry_delivery(delivery_id: UUID) -> dict[str, Any]:
    """Retry a failed delivery."""
    tenant_id = "default-tenant"

    service = WebhookService()
    success = await service.retry_delivery(delivery_id, tenant_id)

    if not success:
        raise HTTPException(status_code=404, detail="Delivery not found")

    return {"retried": True}
```

## Test Cases

```python
# services/agent-service/tests/unit/test_webhooks.py
"""Tests for webhooks."""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, patch, MagicMock

from aswa_agents.webhooks.models import (
    WebhookEvent,
    WebhookStatus,
    WebhookDeliveryStatus,
    WebhookSubscriptionCreate,
)
from aswa_agents.webhooks.service import WebhookService
from aswa_agents.webhooks.repository import WebhookRepository


class TestWebhookService:
    """Test WebhookService."""

    @pytest.fixture
    def service(self):
        return WebhookService()

    @pytest.mark.asyncio
    async def test_create_subscription(self, service):
        """Test creating a subscription."""
        subscription = WebhookSubscriptionCreate(
            name="Test Webhook",
            url="https://example.com/webhook",
            events=[WebhookEvent.EXECUTION_COMPLETED],
        )

        mock_sub = MagicMock()
        mock_sub.id = uuid4()
        mock_sub.name = "Test Webhook"
        mock_sub.url = "https://example.com/webhook"
        mock_sub.description = None
        mock_sub.agent_id = None
        mock_sub.events = ["execution.completed"]
        mock_sub.enabled = True
        mock_sub.status = WebhookStatus.ACTIVE.value
        mock_sub.last_triggered = None
        mock_sub.failure_count = 0
        mock_sub.created_at = datetime.utcnow()

        with patch.object(service._repo, "create_subscription") as mock_create:
            mock_create.return_value = mock_sub

            result = await service.create_subscription(
                "tenant-1", subscription, "user-1"
            )

            assert result["name"] == "Test Webhook"
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_event(self, service):
        """Test dispatching an event."""
        mock_sub = MagicMock()
        mock_sub.id = uuid4()
        mock_sub.retry_count = 3

        mock_delivery = MagicMock()
        mock_delivery.id = uuid4()

        with patch.object(service._repo, "get_matching_subscriptions") as mock_get:
            mock_get.return_value = [mock_sub]

            with patch.object(service._repo, "create_delivery") as mock_create:
                mock_create.return_value = mock_delivery

                count = await service.dispatch_event(
                    tenant_id="tenant-1",
                    event_type=WebhookEvent.EXECUTION_COMPLETED,
                    data={"execution_id": "123"},
                )

                assert count == 1
                mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_webhook_success(self, service):
        """Test sending webhook successfully."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.text = "OK"

            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response

            result = await service._send_webhook(
                url="https://example.com/webhook",
                payload={"event": "test"},
                secret="secret",
                headers={},
                timeout=30,
            )

            assert result["status"] == 200

    @pytest.mark.asyncio
    async def test_send_webhook_with_signature(self, service):
        """Test webhook signature is included."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.text = "OK"

            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            await service._send_webhook(
                url="https://example.com/webhook",
                payload={"event": "test"},
                secret="test-secret",
                headers={},
                timeout=30,
            )

            # Verify signature header was sent
            call_args = mock_instance.post.call_args
            headers = call_args.kwargs.get("headers", {})
            assert "X-Webhook-Signature" in headers

    @pytest.mark.asyncio
    async def test_test_subscription(self, service):
        """Test testing a subscription."""
        mock_sub = MagicMock()
        mock_sub.url = "https://example.com/webhook"
        mock_sub.secret = None
        mock_sub.headers = {}
        mock_sub.timeout_seconds = 30

        with patch.object(service._repo, "get_subscription") as mock_get:
            mock_get.return_value = mock_sub

            with patch.object(service, "_send_webhook") as mock_send:
                mock_send.return_value = {"status": 200, "time_ms": 100}

                result = await service.test_subscription(uuid4(), "tenant-1")

                assert result["success"] is True
                assert result["status_code"] == 200


class TestWebhookRepository:
    """Test WebhookRepository."""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_create_subscription(self, mock_session):
        """Test creating a subscription."""
        repo = WebhookRepository(session=mock_session)

        await repo.create_subscription(
            tenant_id="tenant-1",
            name="Test",
            url="https://example.com/webhook",
            events=["execution.completed"],
        )

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_get_matching_subscriptions(self, mock_session):
        """Test getting matching subscriptions."""
        repo = WebhookRepository(session=mock_session)

        mock_sub = MagicMock()
        mock_sub.events = ["execution.completed", "*"]

        mock_session.execute.return_value = AsyncMock(
            scalars=lambda: AsyncMock(all=lambda: [mock_sub])
        )

        subs = await repo.get_matching_subscriptions(
            tenant_id="tenant-1",
            event_type="execution.completed",
        )

        assert len(subs) == 1

    @pytest.mark.asyncio
    async def test_get_matching_subscriptions_wildcard(self, mock_session):
        """Test wildcard event matching."""
        repo = WebhookRepository(session=mock_session)

        mock_sub = MagicMock()
        mock_sub.events = ["*"]

        mock_session.execute.return_value = AsyncMock(
            scalars=lambda: AsyncMock(all=lambda: [mock_sub])
        )

        subs = await repo.get_matching_subscriptions(
            tenant_id="tenant-1",
            event_type="any.event",
        )

        assert len(subs) == 1


class TestWebhookDelivery:
    """Test webhook delivery."""

    @pytest.fixture
    def service(self):
        return WebhookService()

    def test_get_retry_delay(self, service):
        """Test exponential backoff."""
        assert service._get_retry_delay(1) == 120  # 2 * 60
        assert service._get_retry_delay(2) == 240  # 4 * 60
        assert service._get_retry_delay(10) == 3600  # Max 1 hour

    @pytest.mark.asyncio
    async def test_process_delivery_success(self, service):
        """Test successful delivery processing."""
        delivery_id = uuid4()

        mock_delivery = MagicMock()
        mock_delivery.payload = {"event": "test"}
        mock_delivery.attempt_count = 0
        mock_delivery.max_attempts = 3

        mock_sub = MagicMock()
        mock_sub.url = "https://example.com/webhook"
        mock_sub.secret = None
        mock_sub.headers = {}
        mock_sub.timeout_seconds = 30
        mock_sub.enabled = True
        mock_sub.id = uuid4()

        with patch.object(service._repo, "get_delivery") as mock_get_del:
            mock_get_del.return_value = mock_delivery

            with patch.object(service._repo, "get_subscription_by_id") as mock_get_sub:
                mock_get_sub.return_value = mock_sub

                with patch.object(service, "_send_webhook") as mock_send:
                    mock_send.return_value = {"status": 200, "body": "OK", "time_ms": 50}

                    with patch.object(service._repo, "update_delivery_status") as mock_update:
                        with patch.object(service._repo, "update_subscription_triggered"):
                            await service._process_delivery(delivery_id)

                            mock_update.assert_called_once()
                            call_args = mock_update.call_args
                            assert call_args[0][1] == WebhookDeliveryStatus.SUCCESS.value
```

## Verification Steps

1. **Run unit tests:**
   ```bash
   cd services/agent-service
   pytest tests/unit/test_webhooks.py -v
   ```

2. **Test webhook subscription:**
   ```bash
   # Create subscription
   curl -X POST http://localhost:8000/api/v1/webhooks/subscriptions \
     -H "Content-Type: application/json" \
     -d '{
       "name": "My Webhook",
       "url": "https://example.com/webhook",
       "events": ["execution.completed", "execution.failed"]
     }'

   # Test subscription
   curl -X POST http://localhost:8000/api/v1/webhooks/subscriptions/{id}/test
   ```

3. **Test delivery tracking:**
   ```bash
   # List deliveries
   curl http://localhost:8000/api/v1/webhooks/deliveries

   # Retry failed delivery
   curl -X POST http://localhost:8000/api/v1/webhooks/deliveries/{id}/retry
   ```

## Next Task

Proceed to `task-9.8.4-agent-api.md` for implementing the agent API.
