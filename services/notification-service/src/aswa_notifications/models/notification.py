import uuid
from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, DateTime, JSON, Boolean, Integer, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class NotificationType(str, Enum):
    """Notification types."""
    INSIGHT_ALERT = "insight_alert"
    DIGEST = "digest"
    DOCUMENT_PROCESSED = "document_processed"
    DOCUMENT_FAILED = "document_failed"
    QUERY_RESPONSE = "query_response"
    SYSTEM_ALERT = "system_alert"
    MENTION = "mention"
    SHARE = "share"


class NotificationChannel(str, Enum):
    """Notification channels."""
    EMAIL = "email"
    PUSH = "push"
    IN_APP = "in_app"
    SLACK = "slack"
    TEAMS = "teams"


class DeliveryStatus(str, Enum):
    """Delivery status."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    BOUNCED = "bounced"


class NotificationPriority(str, Enum):
    """Notification priority."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationDB(Base):
    """Database model for notifications."""

    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    type = Column(SQLEnum(NotificationType), nullable=False)
    channel = Column(SQLEnum(NotificationChannel), nullable=False)
    priority = Column(SQLEnum(NotificationPriority), default=NotificationPriority.NORMAL)
    subject = Column(String, nullable=True)
    content = Column(JSON, nullable=False)
    template_id = Column(String, nullable=True)
    template_data = Column(JSON, default={})
    status = Column(SQLEnum(DeliveryStatus), default=DeliveryStatus.PENDING)
    external_id = Column(String, nullable=True)  # ID from external service
    error = Column(String, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    scheduled_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    metadata = Column(JSON, default={})


class NotificationCreate(BaseModel):
    """Schema for creating a notification."""

    user_id: str
    type: NotificationType
    channel: NotificationChannel
    priority: NotificationPriority = NotificationPriority.NORMAL
    subject: str | None = None
    content: dict[str, Any] | None = None
    template_id: str | None = None
    template_data: dict[str, Any] = Field(default_factory=dict)
    scheduled_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class NotificationBatch(BaseModel):
    """Schema for batch notifications."""

    user_ids: list[str]
    type: NotificationType
    channels: list[NotificationChannel]
    priority: NotificationPriority = NotificationPriority.NORMAL
    subject: str | None = None
    template_id: str | None = None
    template_data: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class NotificationResponse(BaseModel):
    """Schema for notification response."""

    id: str
    tenant_id: str
    user_id: str
    type: NotificationType
    channel: NotificationChannel
    priority: NotificationPriority
    subject: str | None
    status: DeliveryStatus
    sent_at: datetime | None
    delivered_at: datetime | None
    read_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
