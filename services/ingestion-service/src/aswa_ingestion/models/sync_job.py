"""Sync job model."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID


class SyncJobStatus(str, Enum):
    """Sync job status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SyncJob:
    """Sync job entity.

    Represents a data source synchronization job.
    """

    id: UUID
    tenant_id: UUID
    data_source_id: UUID
    status: SyncJobStatus
    full_sync: bool = False
    started_at: datetime | None = None
    completed_at: datetime | None = None
    documents_found: int = 0
    documents_processed: int = 0
    documents_failed: int = 0
    error_message: str | None = None
    cursor: str | None = None  # For cursor-based pagination
    metadata: dict = field(default_factory=dict)
