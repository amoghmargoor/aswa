from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Any
from uuid import UUID
import asyncio
import structlog

from .job import ExtractionJob, JobStatus

logger = structlog.get_logger()


@dataclass
class JobProgress:
    """Progress information for a job."""
    job_id: UUID
    status: JobStatus
    total_documents: int
    processed_documents: int
    successful_documents: int
    failed_documents: int
    progress_percentage: float
    current_document: UUID | None = None
    eta_seconds: float | None = None
    messages: list[str] = field(default_factory=list)


class ProgressTracker:
    """Track and report job progress."""

    def __init__(
        self,
        callback: Callable[[JobProgress], Any] | None = None,
        update_interval_seconds: float = 1.0,
    ):
        self.callback = callback
        self.update_interval = update_interval_seconds
        self._progress_cache: dict[UUID, JobProgress] = {}
        self._last_update: dict[UUID, datetime] = {}
        self._start_times: dict[UUID, datetime] = {}
        self._lock = asyncio.Lock()

    async def start_job(self, job: ExtractionJob) -> None:
        """Record job start."""
        async with self._lock:
            self._start_times[job.id] = datetime.utcnow()
            progress = self._create_progress(job)
            self._progress_cache[job.id] = progress
            await self._emit_progress(progress)

    async def update_progress(
        self,
        job: ExtractionJob,
        current_document: UUID | None = None,
        message: str | None = None,
    ) -> None:
        """Update job progress."""
        async with self._lock:
            progress = self._create_progress(job, current_document)

            if message:
                progress.messages.append(message)

            # Calculate ETA
            progress.eta_seconds = self._calculate_eta(job)

            self._progress_cache[job.id] = progress

            # Throttle updates
            last = self._last_update.get(job.id)
            now = datetime.utcnow()
            if last and (now - last).total_seconds() < self.update_interval:
                return

            self._last_update[job.id] = now
            await self._emit_progress(progress)

    async def complete_job(self, job: ExtractionJob) -> None:
        """Record job completion."""
        async with self._lock:
            progress = self._create_progress(job)
            self._progress_cache[job.id] = progress
            await self._emit_progress(progress)

            # Cleanup
            self._start_times.pop(job.id, None)

    def get_progress(self, job_id: UUID) -> JobProgress | None:
        """Get current progress for a job."""
        return self._progress_cache.get(job_id)

    def _create_progress(
        self,
        job: ExtractionJob,
        current_document: UUID | None = None,
    ) -> JobProgress:
        """Create progress object from job."""
        return JobProgress(
            job_id=job.id,
            status=job.status,
            total_documents=job.total_documents,
            processed_documents=job.processed_documents,
            successful_documents=job.successful_documents,
            failed_documents=job.failed_documents,
            progress_percentage=job.progress_percentage,
            current_document=current_document,
        )

    def _calculate_eta(self, job: ExtractionJob) -> float | None:
        """Calculate estimated time remaining."""
        start_time = self._start_times.get(job.id)
        if not start_time or job.processed_documents == 0:
            return None

        elapsed = (datetime.utcnow() - start_time).total_seconds()
        docs_per_second = job.processed_documents / elapsed
        remaining_docs = job.total_documents - job.processed_documents

        if docs_per_second > 0:
            return remaining_docs / docs_per_second
        return None

    async def _emit_progress(self, progress: JobProgress) -> None:
        """Emit progress update via callback."""
        if self.callback:
            try:
                result = self.callback(progress)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error("Progress callback failed", error=str(e))
