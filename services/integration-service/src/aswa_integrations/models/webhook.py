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
