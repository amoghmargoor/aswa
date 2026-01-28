from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, IntEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Status of an extraction job."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIALLY_COMPLETED = "partially_completed"


class JobPriority(IntEnum):
    """Priority levels for jobs."""
    LOW = 0
    NORMAL = 5
    HIGH = 10
    URGENT = 20


class ExtractionJob(BaseModel):
    """An extraction job to be processed."""
    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    document_ids: list[UUID]
    extraction_types: list[str] = Field(default=["entity", "risk", "opportunity", "pattern"])
    priority: JobPriority = JobPriority.NORMAL
    context: dict[str, Any] = Field(default_factory=dict)

    # Status tracking
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Progress tracking
    total_documents: int = 0
    processed_documents: int = 0
    successful_documents: int = 0
    failed_documents: int = 0

    # Results
    results: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)

    # Options
    force_reextract: bool = False
    callback_url: str | None = None
    max_retries: int = 3

    def model_post_init(self, __context) -> None:
        if self.total_documents == 0:
            self.total_documents = len(self.document_ids)

    @property
    def progress_percentage(self) -> float:
        if self.total_documents == 0:
            return 0.0
        return (self.processed_documents / self.total_documents) * 100

    @property
    def is_complete(self) -> bool:
        return self.status in [
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
            JobStatus.PARTIALLY_COMPLETED,
        ]

    @property
    def duration_seconds(self) -> float | None:
        if not self.started_at:
            return None
        end = self.completed_at or datetime.utcnow()
        return (end - self.started_at).total_seconds()

    def start(self) -> None:
        """Mark job as started."""
        self.status = JobStatus.RUNNING
        self.started_at = datetime.utcnow()

    def complete(self) -> None:
        """Mark job as completed."""
        self.completed_at = datetime.utcnow()
        if self.failed_documents == 0:
            self.status = JobStatus.COMPLETED
        elif self.successful_documents > 0:
            self.status = JobStatus.PARTIALLY_COMPLETED
        else:
            self.status = JobStatus.FAILED

    def fail(self, error: str) -> None:
        """Mark job as failed."""
        self.status = JobStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.errors.append(error)

    def cancel(self) -> None:
        """Mark job as cancelled."""
        self.status = JobStatus.CANCELLED
        self.completed_at = datetime.utcnow()

    def add_document_result(self, document_id: UUID, success: bool, result: Any = None, error: str | None = None) -> None:
        """Add result for a processed document."""
        self.processed_documents += 1
        if success:
            self.successful_documents += 1
            if result:
                self.results[str(document_id)] = result
        else:
            self.failed_documents += 1
            if error:
                self.errors.append(f"{document_id}: {error}")


class JobSummary(BaseModel):
    """Summary of a job for API responses."""
    id: UUID
    tenant_id: UUID
    status: JobStatus
    priority: JobPriority
    total_documents: int
    processed_documents: int
    successful_documents: int
    failed_documents: int
    progress_percentage: float
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    duration_seconds: float | None

    @classmethod
    def from_job(cls, job: ExtractionJob) -> "JobSummary":
        return cls(
            id=job.id,
            tenant_id=job.tenant_id,
            status=job.status,
            priority=job.priority,
            total_documents=job.total_documents,
            processed_documents=job.processed_documents,
            successful_documents=job.successful_documents,
            failed_documents=job.failed_documents,
            progress_percentage=job.progress_percentage,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            duration_seconds=job.duration_seconds,
        )
