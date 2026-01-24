"""Framework models for connectors."""

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ConnectorType(str, Enum):
    """Types of data source connectors."""

    GMAIL = "gmail"
    GOOGLE_DRIVE = "google_drive"
    SLACK = "slack"
    SALESFORCE = "salesforce"
    CONFLUENCE = "confluence"
    JIRA = "jira"
    NOTION = "notion"
    SHAREPOINT = "sharepoint"
    DROPBOX = "dropbox"
    HUBSPOT = "hubspot"


class ConnectorDefinition(BaseModel):
    """Definition of an available connector."""

    type: ConnectorType
    name: str
    description: str
    icon_url: str | None = None
    auth_type: Literal["oauth", "api_key", "basic", "none"]
    oauth_provider: str | None = None  # google, slack, salesforce, etc.
    scopes: list[str] = Field(default_factory=list)
    config_schema: dict[str, Any] = Field(default_factory=dict)
    supported_sync_modes: list[str] = Field(
        default_factory=lambda: ["full_refresh", "incremental"]
    )


class OAuthCredentials(BaseModel):
    """OAuth credentials for a connection."""

    access_token: str
    refresh_token: str | None = None
    token_type: str = "Bearer"
    expires_at: datetime | None = None
    scope: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class ConnectionConfig(BaseModel):
    """Configuration for creating/updating a connection."""

    connector_type: ConnectorType
    name: str
    credentials: OAuthCredentials | dict[str, Any]
    config: dict[str, Any] = Field(default_factory=dict)
    sync_schedule: str | None = None  # Cron expression
    sync_mode: Literal["full_refresh", "incremental"] = "incremental"


class ConnectionStatus(str, Enum):
    """Status of a connection."""

    PENDING = "pending"
    ACTIVE = "active"
    ERROR = "error"
    DISABLED = "disabled"


class Connection(BaseModel):
    """A configured data source connection."""

    id: UUID
    tenant_id: UUID
    connector_type: ConnectorType
    name: str
    status: ConnectionStatus
    config: dict[str, Any] = Field(default_factory=dict)
    sync_schedule: str | None = None
    sync_mode: str = "incremental"
    last_sync_at: datetime | None = None
    next_sync_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    # Provider-specific IDs (for mapping)
    provider_source_id: str | None = None
    provider_connection_id: str | None = None


class ConnectionTestResult(BaseModel):
    """Result of testing a connection."""

    success: bool
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class SyncJobStatus(str, Enum):
    """Status of a sync job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SyncJob(BaseModel):
    """A sync job for a connection."""

    id: UUID
    connection_id: UUID
    tenant_id: UUID
    status: SyncJobStatus
    sync_mode: str = "incremental"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    records_synced: int = 0
    bytes_synced: int = 0
    error_message: str | None = None

    # Provider-specific ID
    provider_job_id: str | None = None


class SyncRecord(BaseModel):
    """A single record from a sync."""

    stream: str  # e.g., "emails", "files", "messages"
    data: dict[str, Any]
    emitted_at: datetime = Field(default_factory=datetime.utcnow)

    # For documents
    content: bytes | None = None
    content_type: str | None = None
    filename: str | None = None


class SyncProgress(BaseModel):
    """Progress update for a sync job."""

    job_id: UUID
    status: SyncJobStatus
    records_synced: int = 0
    bytes_synced: int = 0
    current_stream: str | None = None
    message: str | None = None
