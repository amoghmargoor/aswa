from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, DateTime, JSON, Boolean, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
import uuid

Base = declarative_base()


class IntegrationType(str, Enum):
    """Supported integration types."""
    JIRA = "jira"
    WEBHOOK = "webhook"
    SLACK = "slack"
    TEAMS = "teams"
    EMAIL = "email"


class IntegrationStatus(str, Enum):
    """Integration connection status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    PENDING = "pending"


class IntegrationDB(Base):
    """Database model for integrations."""

    __tablename__ = "integrations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    type = Column(SQLEnum(IntegrationType), nullable=False)
    status = Column(SQLEnum(IntegrationStatus), default=IntegrationStatus.PENDING)
    config = Column(JSON, default={})
    credentials_id = Column(String, nullable=True)  # Reference to encrypted credentials
    last_health_check = Column(DateTime, nullable=True)
    last_error = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_enabled = Column(Boolean, default=True)


class IntegrationCreate(BaseModel):
    """Schema for creating an integration."""

    name: str = Field(..., min_length=1, max_length=255)
    type: IntegrationType
    config: dict[str, Any] = Field(default_factory=dict)
    credentials: dict[str, str] | None = None


class IntegrationUpdate(BaseModel):
    """Schema for updating an integration."""

    name: str | None = None
    config: dict[str, Any] | None = None
    credentials: dict[str, str] | None = None
    is_enabled: bool | None = None


class IntegrationResponse(BaseModel):
    """Schema for integration response."""

    id: str
    tenant_id: str
    name: str
    type: IntegrationType
    status: IntegrationStatus
    config: dict[str, Any]
    last_health_check: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime
    is_enabled: bool

    model_config = {"from_attributes": True}


class IntegrationHealth(BaseModel):
    """Integration health status."""

    integration_id: str
    status: IntegrationStatus
    latency_ms: float | None = None
    last_check: datetime
    error: str | None = None
