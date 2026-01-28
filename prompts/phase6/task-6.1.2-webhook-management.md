# Task 6.1.2: Integration Service - Webhook Management

## Context

You are working on the ASWA integration service at `/services/integration-service/`. The service setup is complete (Task 6.1.1). Now we need to implement webhook management for outbound and inbound webhooks.

## Objective

Create webhook management that:
1. Manages outbound webhook registrations
2. Handles inbound webhook validation
3. Provides retry logic for failed deliveries
4. Tracks delivery status and history
5. Supports webhook signatures for security

## Requirements

### 1. Create `/services/integration-service/src/aswa_integrations/models/webhook.py`
```python
from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import Column, String, DateTime, JSON, Boolean, Integer, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
import uuid

from aswa_integrations.models.integration import Base


class WebhookEventType(str, Enum):
    """Supported webhook event types."""
    INSIGHT_CREATED = "insight.created"
    INSIGHT_UPDATED = "insight.updated"
    DOCUMENT_PROCESSED = "document.processed"
    DOCUMENT_FAILED = "document.failed"
    QUERY_COMPLETED = "query.completed"
    DIGEST_READY = "digest.ready"
    ALERT_TRIGGERED = "alert.triggered"


class DeliveryStatus(str, Enum):
    """Webhook delivery status."""
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


class WebhookDB(Base):
    """Database model for webhooks."""

    __tablename__ = "webhooks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    secret = Column(String, nullable=True)  # Stored encrypted
    events = Column(JSON, default=[])  # List of event types
    headers = Column(JSON, default={})  # Custom headers
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Stats
    total_deliveries = Column(Integer, default=0)
    successful_deliveries = Column(Integer, default=0)
    failed_deliveries = Column(Integer, default=0)
    last_delivery_at = Column(DateTime, nullable=True)
    last_error = Column(String, nullable=True)


class WebhookDeliveryDB(Base):
    """Database model for webhook delivery attempts."""

    __tablename__ = "webhook_deliveries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    webhook_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    event_type = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    status = Column(SQLEnum(DeliveryStatus), default=DeliveryStatus.PENDING)
    attempt_count = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    response_status = Column(Integer, nullable=True)
    response_body = Column(String, nullable=True)
    error = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    delivered_at = Column(DateTime, nullable=True)
    next_retry_at = Column(DateTime, nullable=True)


class WebhookCreate(BaseModel):
    """Schema for creating a webhook."""

    name: str = Field(..., min_length=1, max_length=255)
    url: HttpUrl
    secret: str | None = None
    events: list[WebhookEventType] = Field(default_factory=list)
    headers: dict[str, str] = Field(default_factory=dict)


class WebhookUpdate(BaseModel):
    """Schema for updating a webhook."""

    name: str | None = None
    url: HttpUrl | None = None
    secret: str | None = None
    events: list[WebhookEventType] | None = None
    headers: dict[str, str] | None = None
    is_active: bool | None = None


class WebhookResponse(BaseModel):
    """Schema for webhook response."""

    id: str
    tenant_id: str
    name: str
    url: str
    events: list[str]
    headers: dict[str, str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    total_deliveries: int
    successful_deliveries: int
    failed_deliveries: int
    last_delivery_at: datetime | None
    last_error: str | None

    model_config = {"from_attributes": True}


class WebhookDeliveryResponse(BaseModel):
    """Schema for delivery response."""

    id: str
    webhook_id: str
    event_type: str
    status: DeliveryStatus
    attempt_count: int
    response_status: int | None
    error: str | None
    created_at: datetime
    delivered_at: datetime | None

    model_config = {"from_attributes": True}


class WebhookEvent(BaseModel):
    """Webhook event payload."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: WebhookEventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    tenant_id: str
    data: dict[str, Any]
```

### 2. Create `/services/integration-service/src/aswa_integrations/services/webhook_manager.py`
```python
import uuid
import hashlib
import hmac
import json
from datetime import datetime, timedelta
from typing import Any
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
import httpx
import structlog

from aswa_integrations.config import get_settings
from aswa_integrations.models.webhook import (
    WebhookDB,
    WebhookDeliveryDB,
    WebhookCreate,
    WebhookUpdate,
    WebhookResponse,
    WebhookDeliveryResponse,
    WebhookEvent,
    WebhookEventType,
    DeliveryStatus,
    Base,
)
from aswa_integrations.services.credential_manager import CredentialManager

logger = structlog.get_logger()


class WebhookManager:
    """Manages webhook registrations and deliveries."""

    def __init__(self):
        self.settings = get_settings()
        self.credential_manager = CredentialManager()
        self._engine = None
        self._session_factory = None

    async def initialize(self) -> None:
        """Initialize the webhook manager."""
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

        await self.credential_manager.initialize()
        logger.info("Webhook manager initialized")

    async def close(self) -> None:
        """Close connections."""
        await self.credential_manager.close()
        if self._engine:
            await self._engine.dispose()

    def _get_session(self) -> AsyncSession:
        """Get a database session."""
        if not self._session_factory:
            raise RuntimeError("Webhook manager not initialized")
        return self._session_factory()

    async def create_webhook(
        self,
        tenant_id: str,
        data: WebhookCreate,
    ) -> WebhookResponse:
        """Create a new webhook.

        Args:
            tenant_id: Tenant identifier
            data: Webhook creation data

        Returns:
            Created webhook
        """
        webhook_id = str(uuid.uuid4())

        # Store secret if provided
        secret_id = None
        if data.secret:
            secret_id = f"webhook:{webhook_id}"
            await self.credential_manager.store_credentials(
                secret_id,
                {"secret": data.secret},
            )

        webhook = WebhookDB(
            id=webhook_id,
            tenant_id=tenant_id,
            name=data.name,
            url=str(data.url),
            secret=secret_id,
            events=[e.value for e in data.events],
            headers=data.headers,
        )

        async with self._get_session() as session:
            session.add(webhook)
            await session.commit()
            await session.refresh(webhook)

        logger.info(
            "Webhook created",
            webhook_id=webhook_id,
            tenant_id=tenant_id,
        )

        return WebhookResponse.model_validate(webhook)

    async def get_webhook(
        self,
        tenant_id: str,
        webhook_id: str,
    ) -> WebhookResponse | None:
        """Get a webhook by ID.

        Args:
            tenant_id: Tenant identifier
            webhook_id: Webhook identifier

        Returns:
            Webhook or None
        """
        async with self._get_session() as session:
            result = await session.execute(
                select(WebhookDB).where(
                    WebhookDB.id == webhook_id,
                    WebhookDB.tenant_id == tenant_id,
                )
            )
            webhook = result.scalar_one_or_none()

            if webhook:
                return WebhookResponse.model_validate(webhook)
            return None

    async def list_webhooks(
        self,
        tenant_id: str,
        event_type: WebhookEventType | None = None,
        is_active: bool | None = None,
    ) -> list[WebhookResponse]:
        """List webhooks for a tenant.

        Args:
            tenant_id: Tenant identifier
            event_type: Optional event type filter
            is_active: Optional active status filter

        Returns:
            List of webhooks
        """
        async with self._get_session() as session:
            query = select(WebhookDB).where(WebhookDB.tenant_id == tenant_id)

            if is_active is not None:
                query = query.where(WebhookDB.is_active == is_active)

            result = await session.execute(query)
            webhooks = result.scalars().all()

            # Filter by event type if specified
            if event_type:
                webhooks = [
                    w for w in webhooks
                    if event_type.value in w.events
                ]

            return [WebhookResponse.model_validate(w) for w in webhooks]

    async def update_webhook(
        self,
        tenant_id: str,
        webhook_id: str,
        data: WebhookUpdate,
    ) -> WebhookResponse | None:
        """Update a webhook.

        Args:
            tenant_id: Tenant identifier
            webhook_id: Webhook identifier
            data: Update data

        Returns:
            Updated webhook or None
        """
        async with self._get_session() as session:
            result = await session.execute(
                select(WebhookDB).where(
                    WebhookDB.id == webhook_id,
                    WebhookDB.tenant_id == tenant_id,
                )
            )
            webhook = result.scalar_one_or_none()

            if not webhook:
                return None

            if data.name is not None:
                webhook.name = data.name
            if data.url is not None:
                webhook.url = str(data.url)
            if data.events is not None:
                webhook.events = [e.value for e in data.events]
            if data.headers is not None:
                webhook.headers = data.headers
            if data.is_active is not None:
                webhook.is_active = data.is_active

            # Update secret if provided
            if data.secret is not None:
                secret_id = webhook.secret or f"webhook:{webhook_id}"
                await self.credential_manager.store_credentials(
                    secret_id,
                    {"secret": data.secret},
                )
                webhook.secret = secret_id

            webhook.updated_at = datetime.utcnow()

            await session.commit()
            await session.refresh(webhook)

            return WebhookResponse.model_validate(webhook)

    async def delete_webhook(
        self,
        tenant_id: str,
        webhook_id: str,
    ) -> bool:
        """Delete a webhook.

        Args:
            tenant_id: Tenant identifier
            webhook_id: Webhook identifier

        Returns:
            True if deleted
        """
        async with self._get_session() as session:
            result = await session.execute(
                select(WebhookDB).where(
                    WebhookDB.id == webhook_id,
                    WebhookDB.tenant_id == tenant_id,
                )
            )
            webhook = result.scalar_one_or_none()

            if not webhook:
                return False

            # Delete secret
            if webhook.secret:
                await self.credential_manager.delete_credentials(webhook.secret)

            await session.delete(webhook)
            await session.commit()

            return True

    async def dispatch_event(
        self,
        event: WebhookEvent,
    ) -> list[str]:
        """Dispatch an event to all matching webhooks.

        Args:
            event: Event to dispatch

        Returns:
            List of delivery IDs
        """
        # Find matching webhooks
        async with self._get_session() as session:
            result = await session.execute(
                select(WebhookDB).where(
                    WebhookDB.tenant_id == event.tenant_id,
                    WebhookDB.is_active == True,
                )
            )
            webhooks = result.scalars().all()

        # Filter by event type
        matching = [
            w for w in webhooks
            if event.type.value in w.events or not w.events
        ]

        # Create delivery records
        delivery_ids = []
        for webhook in matching:
            delivery_id = await self._create_delivery(webhook, event)
            delivery_ids.append(delivery_id)

        logger.info(
            "Event dispatched",
            event_type=event.type,
            webhook_count=len(matching),
        )

        return delivery_ids

    async def _create_delivery(
        self,
        webhook: WebhookDB,
        event: WebhookEvent,
    ) -> str:
        """Create a delivery record and attempt delivery.

        Args:
            webhook: Target webhook
            event: Event to deliver

        Returns:
            Delivery ID
        """
        delivery_id = str(uuid.uuid4())

        payload = {
            "id": event.id,
            "type": event.type.value,
            "timestamp": event.timestamp.isoformat(),
            "data": event.data,
        }

        delivery = WebhookDeliveryDB(
            id=delivery_id,
            webhook_id=webhook.id,
            event_type=event.type.value,
            payload=payload,
            status=DeliveryStatus.PENDING,
        )

        async with self._get_session() as session:
            session.add(delivery)
            await session.commit()

        # Attempt delivery
        await self._deliver(webhook, delivery)

        return delivery_id

    async def _deliver(
        self,
        webhook: WebhookDB,
        delivery: WebhookDeliveryDB,
    ) -> None:
        """Attempt to deliver a webhook.

        Args:
            webhook: Target webhook
            delivery: Delivery record
        """
        # Get secret if configured
        secret = None
        if webhook.secret:
            creds = await self.credential_manager.get_credentials(webhook.secret)
            if creds:
                secret = creds.get("secret")

        # Build headers
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "ASWA-Webhook/1.0",
            "X-Webhook-ID": str(webhook.id),
            "X-Delivery-ID": str(delivery.id),
            **webhook.headers,
        }

        # Add signature if secret is configured
        payload_bytes = json.dumps(delivery.payload, sort_keys=True).encode()
        if secret:
            signature = hmac.new(
                secret.encode(),
                payload_bytes,
                hashlib.sha256,
            ).hexdigest()
            headers["X-ASWA-Signature"] = f"sha256={signature}"

        # Attempt delivery
        async with self._get_session() as session:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        webhook.url,
                        content=payload_bytes,
                        headers=headers,
                    )

                    delivery.response_status = response.status_code
                    delivery.response_body = response.text[:1000]  # Limit size
                    delivery.attempt_count += 1

                    if response.is_success:
                        delivery.status = DeliveryStatus.DELIVERED
                        delivery.delivered_at = datetime.utcnow()

                        # Update webhook stats
                        await session.execute(
                            update(WebhookDB)
                            .where(WebhookDB.id == webhook.id)
                            .values(
                                total_deliveries=WebhookDB.total_deliveries + 1,
                                successful_deliveries=WebhookDB.successful_deliveries + 1,
                                last_delivery_at=datetime.utcnow(),
                            )
                        )
                    else:
                        await self._handle_failure(
                            session, webhook, delivery,
                            f"HTTP {response.status_code}",
                        )

            except Exception as e:
                delivery.attempt_count += 1
                await self._handle_failure(session, webhook, delivery, str(e))

            session.add(delivery)
            await session.commit()

    async def _handle_failure(
        self,
        session: AsyncSession,
        webhook: WebhookDB,
        delivery: WebhookDeliveryDB,
        error: str,
    ) -> None:
        """Handle delivery failure.

        Args:
            session: Database session
            webhook: Target webhook
            delivery: Delivery record
            error: Error message
        """
        delivery.error = error

        if delivery.attempt_count < delivery.max_attempts:
            # Schedule retry with exponential backoff
            delay = 60 * (2 ** (delivery.attempt_count - 1))  # 1, 2, 4 minutes
            delivery.status = DeliveryStatus.RETRYING
            delivery.next_retry_at = datetime.utcnow() + timedelta(seconds=delay)

            logger.info(
                "Webhook delivery scheduled for retry",
                delivery_id=str(delivery.id),
                attempt=delivery.attempt_count,
                next_retry=delivery.next_retry_at,
            )
        else:
            delivery.status = DeliveryStatus.FAILED

            # Update webhook stats
            await session.execute(
                update(WebhookDB)
                .where(WebhookDB.id == webhook.id)
                .values(
                    total_deliveries=WebhookDB.total_deliveries + 1,
                    failed_deliveries=WebhookDB.failed_deliveries + 1,
                    last_error=error,
                )
            )

            logger.error(
                "Webhook delivery failed permanently",
                delivery_id=str(delivery.id),
                error=error,
            )

    async def retry_pending_deliveries(self) -> int:
        """Retry pending deliveries that are due.

        Returns:
            Number of retries attempted
        """
        async with self._get_session() as session:
            result = await session.execute(
                select(WebhookDeliveryDB).where(
                    WebhookDeliveryDB.status == DeliveryStatus.RETRYING,
                    WebhookDeliveryDB.next_retry_at <= datetime.utcnow(),
                )
            )
            deliveries = result.scalars().all()

            count = 0
            for delivery in deliveries:
                # Get webhook
                wh_result = await session.execute(
                    select(WebhookDB).where(WebhookDB.id == delivery.webhook_id)
                )
                webhook = wh_result.scalar_one_or_none()

                if webhook and webhook.is_active:
                    await self._deliver(webhook, delivery)
                    count += 1

            return count

    async def get_delivery_history(
        self,
        tenant_id: str,
        webhook_id: str,
        limit: int = 50,
    ) -> list[WebhookDeliveryResponse]:
        """Get delivery history for a webhook.

        Args:
            tenant_id: Tenant identifier
            webhook_id: Webhook identifier
            limit: Maximum number of records

        Returns:
            List of deliveries
        """
        # Verify webhook ownership
        webhook = await self.get_webhook(tenant_id, webhook_id)
        if not webhook:
            return []

        async with self._get_session() as session:
            result = await session.execute(
                select(WebhookDeliveryDB)
                .where(WebhookDeliveryDB.webhook_id == webhook_id)
                .order_by(WebhookDeliveryDB.created_at.desc())
                .limit(limit)
            )
            deliveries = result.scalars().all()

            return [
                WebhookDeliveryResponse.model_validate(d)
                for d in deliveries
            ]
```

### 3. Create `/services/integration-service/src/aswa_integrations/api/webhook_routes.py`
```python
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
```

### 4. Create `/services/integration-service/src/aswa_integrations/services/webhook_validator.py`
```python
import hashlib
import hmac
import time
from typing import Any
import structlog

logger = structlog.get_logger()


class WebhookValidator:
    """Validates incoming webhook requests."""

    def __init__(self, signing_secret: str, tolerance: int = 300):
        """Initialize validator.

        Args:
            signing_secret: Secret for signature validation
            tolerance: Timestamp tolerance in seconds
        """
        self.signing_secret = signing_secret
        self.tolerance = tolerance

    def validate_signature(
        self,
        payload: bytes,
        signature: str,
        timestamp: str | None = None,
    ) -> bool:
        """Validate webhook signature.

        Args:
            payload: Raw request body
            signature: Signature from header
            timestamp: Optional timestamp from header

        Returns:
            True if signature is valid

        Raises:
            ValueError if validation fails
        """
        # Validate timestamp if provided
        if timestamp:
            try:
                ts = int(timestamp)
                if abs(time.time() - ts) > self.tolerance:
                    raise ValueError("Timestamp outside tolerance window")
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid timestamp: {e}")

        # Parse signature
        if signature.startswith("sha256="):
            signature = signature[7:]

        # Compute expected signature
        if timestamp:
            signing_payload = f"{timestamp}:{payload.decode()}"
        else:
            signing_payload = payload.decode()

        expected = hmac.new(
            self.signing_secret.encode(),
            signing_payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        # Constant-time comparison
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid signature")

        return True

    def generate_signature(
        self,
        payload: bytes,
        timestamp: int | None = None,
    ) -> tuple[str, int]:
        """Generate a webhook signature.

        Args:
            payload: Request body
            timestamp: Optional timestamp (defaults to current time)

        Returns:
            Tuple of (signature, timestamp)
        """
        ts = timestamp or int(time.time())
        signing_payload = f"{ts}:{payload.decode()}"

        signature = hmac.new(
            self.signing_secret.encode(),
            signing_payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        return f"sha256={signature}", ts


class InboundWebhookHandler:
    """Handles inbound webhooks from external services."""

    def __init__(self):
        self._handlers: dict[str, callable] = {}

    def register_handler(
        self,
        source: str,
        handler: callable,
    ) -> None:
        """Register a handler for a webhook source.

        Args:
            source: Webhook source identifier
            handler: Async handler function
        """
        self._handlers[source] = handler
        logger.info("Webhook handler registered", source=source)

    async def handle(
        self,
        source: str,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        """Handle an inbound webhook.

        Args:
            source: Webhook source
            payload: Request payload
            headers: Request headers

        Returns:
            Handler response
        """
        handler = self._handlers.get(source)
        if not handler:
            raise ValueError(f"No handler for source: {source}")

        logger.info("Processing inbound webhook", source=source)

        try:
            result = await handler(payload, headers)
            return {"status": "processed", "result": result}
        except Exception as e:
            logger.error(
                "Inbound webhook handler failed",
                source=source,
                error=str(e),
            )
            raise
```

### 5. Update `/services/integration-service/src/aswa_integrations/main.py`
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from aswa_integrations.config import get_settings
from aswa_integrations.api.routes import router as integration_router
from aswa_integrations.api.webhook_routes import router as webhook_router, set_webhook_manager
from aswa_integrations.api.dependencies import set_integration_manager
from aswa_integrations.services.integration_manager import IntegrationManager
from aswa_integrations.services.webhook_manager import WebhookManager

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    settings = get_settings()

    # Initialize integration manager
    integration_manager = IntegrationManager()
    await integration_manager.initialize()
    set_integration_manager(integration_manager)

    # Initialize webhook manager
    webhook_manager = WebhookManager()
    await webhook_manager.initialize()
    set_webhook_manager(webhook_manager)

    logger.info(
        "Integration service started",
        environment=settings.environment,
    )

    yield

    # Cleanup
    await integration_manager.close()
    await webhook_manager.close()
    logger.info("Integration service stopped")


def create_app() -> FastAPI:
    """Create the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="ASWA Integration Service",
        description="Manages external integrations and webhooks for ASWA",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(integration_router, prefix="/api/v1")
    app.include_router(webhook_router, prefix="/api/v1")

    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "service": settings.service_name}

    return app


app = create_app()
```

## Test Requirements

### Create `/services/integration-service/tests/test_webhook_manager.py`
```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from aswa_integrations.services.webhook_manager import WebhookManager
from aswa_integrations.models.webhook import (
    WebhookCreate,
    WebhookEventType,
    WebhookEvent,
)


class TestWebhookManager:
    @pytest.fixture
    def manager(self):
        """Create a webhook manager instance."""
        return WebhookManager()

    @pytest.mark.asyncio
    async def test_dispatch_event(self, manager):
        """Test event dispatching."""
        event = WebhookEvent(
            type=WebhookEventType.INSIGHT_CREATED,
            tenant_id="test-tenant",
            data={"insight_id": "123"},
        )

        with patch.object(manager, '_get_session') as mock_session, \
             patch.object(manager, '_create_delivery', new_callable=AsyncMock) as mock_create:

            session = AsyncMock()
            result = MagicMock()
            result.scalars.return_value.all.return_value = []
            session.execute = AsyncMock(return_value=result)
            mock_session.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_session.return_value.__aexit__ = AsyncMock()

            delivery_ids = await manager.dispatch_event(event)

            assert isinstance(delivery_ids, list)


class TestWebhookValidator:
    def test_validate_signature(self):
        """Test signature validation."""
        from aswa_integrations.services.webhook_validator import WebhookValidator

        validator = WebhookValidator("test-secret")
        payload = b'{"test": "data"}'

        signature, timestamp = validator.generate_signature(payload)

        # Should validate successfully
        result = validator.validate_signature(
            payload,
            signature,
            str(timestamp),
        )

        assert result is True

    def test_invalid_signature(self):
        """Test invalid signature rejection."""
        from aswa_integrations.services.webhook_validator import WebhookValidator

        validator = WebhookValidator("test-secret")
        payload = b'{"test": "data"}'

        with pytest.raises(ValueError, match="Invalid signature"):
            validator.validate_signature(
                payload,
                "sha256=invalid",
            )

    def test_generate_signature(self):
        """Test signature generation."""
        from aswa_integrations.services.webhook_validator import WebhookValidator

        validator = WebhookValidator("test-secret")
        payload = b'{"test": "data"}'

        signature, timestamp = validator.generate_signature(payload)

        assert signature.startswith("sha256=")
        assert isinstance(timestamp, int)
```

## Verification

1. Run tests: `pytest tests/test_webhook_manager.py -v`
2. Test webhook creation via API
3. Test event dispatching
4. Verify retry logic works correctly
5. Test signature validation
