import pytest
from uuid import uuid4
from datetime import datetime

from aswa_insight.batch.job import ExtractionJob, JobStatus, JobPriority, JobSummary


class TestExtractionJob:
    def test_create_job(self):
        """Test job creation."""
        job = ExtractionJob(
            tenant_id=uuid4(),
            document_ids=[uuid4(), uuid4()],
        )
        assert job.status == JobStatus.PENDING
        assert job.total_documents == 2
        assert job.progress_percentage == 0.0

    def test_job_start(self):
        """Test starting a job."""
        job = ExtractionJob(tenant_id=uuid4(), document_ids=[uuid4()])
        job.start()
        assert job.status == JobStatus.RUNNING
        assert job.started_at is not None

    def test_job_complete_success(self):
        """Test successful completion."""
        job = ExtractionJob(tenant_id=uuid4(), document_ids=[uuid4()])
        job.start()
        job.add_document_result(job.document_ids[0], success=True, result={"test": "data"})
        job.complete()
        assert job.status == JobStatus.COMPLETED
        assert job.successful_documents == 1

    def test_job_complete_partial(self):
        """Test partial completion."""
        job = ExtractionJob(tenant_id=uuid4(), document_ids=[uuid4(), uuid4()])
        job.start()
        job.add_document_result(job.document_ids[0], success=True)
        job.add_document_result(job.document_ids[1], success=False, error="Failed")
        job.complete()
        assert job.status == JobStatus.PARTIALLY_COMPLETED

    def test_job_complete_all_failed(self):
        """Test all documents failed."""
        job = ExtractionJob(tenant_id=uuid4(), document_ids=[uuid4()])
        job.start()
        job.add_document_result(job.document_ids[0], success=False, error="Failed")
        job.complete()
        assert job.status == JobStatus.FAILED

    def test_job_cancel(self):
        """Test job cancellation."""
        job = ExtractionJob(tenant_id=uuid4(), document_ids=[uuid4()])
        job.cancel()
        assert job.status == JobStatus.CANCELLED
        assert job.is_complete

    def test_progress_percentage(self):
        """Test progress calculation."""
        job = ExtractionJob(tenant_id=uuid4(), document_ids=[uuid4()] * 4)
        job.processed_documents = 2
        assert job.progress_percentage == 50.0

    def test_duration_calculation(self):
        """Test duration calculation."""
        job = ExtractionJob(tenant_id=uuid4(), document_ids=[uuid4()])
        job.start()
        # Duration should be calculable
        assert job.duration_seconds is not None


class TestJobSummary:
    def test_from_job(self):
        """Test creating summary from job."""
        job = ExtractionJob(
            tenant_id=uuid4(),
            document_ids=[uuid4()],
            priority=JobPriority.HIGH,
        )
        summary = JobSummary.from_job(job)
        assert summary.id == job.id
        assert summary.priority == JobPriority.HIGH
