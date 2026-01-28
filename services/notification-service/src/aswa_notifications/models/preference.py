import uuid
from datetime import datetime
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, DateTime, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID

from aswa_notifications.models.notification import Base, NotificationType, NotificationChannel


class NotificationPreferenceDB(Base):
    """Database model for notification preferences."""

    __tablename__ = "notification_preferences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)

    # Global settings
    notifications_enabled = Column(Boolean, default=True)
    email_enabled = Column(Boolean, default=True)
    push_enabled = Column(Boolean, default=True)
    in_app_enabled = Column(Boolean, default=True)

    # Per-type settings
    type_preferences = Column(JSON, default={})  # {type: {channel: bool}}

    # Quiet hours
    quiet_hours_enabled = Column(Boolean, default=False)
    quiet_hours_start = Column(String, nullable=True)  # "22:00"
    quiet_hours_end = Column(String, nullable=True)  # "08:00"
    quiet_hours_timezone = Column(String, default="UTC")

    # Digest settings
    digest_frequency = Column(String, default="daily")  # daily, weekly, none
    digest_time = Column(String, default="09:00")
    digest_timezone = Column(String, default="UTC")

    # Contact info
    email_address = Column(String, nullable=True)
    push_tokens = Column(JSON, default=[])  # List of device tokens

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PreferenceUpdate(BaseModel):
    """Schema for updating preferences."""

    notifications_enabled: bool | None = None
    email_enabled: bool | None = None
    push_enabled: bool | None = None
    in_app_enabled: bool | None = None
    type_preferences: dict[str, dict[str, bool]] | None = None
    quiet_hours_enabled: bool | None = None
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    quiet_hours_timezone: str | None = None
    digest_frequency: str | None = None
    digest_time: str | None = None
    digest_timezone: str | None = None
    email_address: str | None = None


class PreferenceResponse(BaseModel):
    """Schema for preference response."""

    id: str
    user_id: str
    notifications_enabled: bool
    email_enabled: bool
    push_enabled: bool
    in_app_enabled: bool
    type_preferences: dict[str, dict[str, bool]]
    quiet_hours_enabled: bool
    quiet_hours_start: str | None
    quiet_hours_end: str | None
    quiet_hours_timezone: str
    digest_frequency: str
    digest_time: str
    digest_timezone: str
    email_address: str | None

    model_config = {"from_attributes": True}
