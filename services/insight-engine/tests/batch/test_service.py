import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from aswa_insight.batch.service import BatchExtractionService
from aswa_insight.batch.job import JobPriority, JobStatus
from aswa_insight.extraction.processor import ExtractionProcessor, ProcessingResult


class TestBatchExtractionService:
    @pytest.fixture
    def mock_processor(self):
        processor = MagicMock(spec=ExtractionProcessor)
        processor.process_document = AsyncMock(return_value=ProcessingResult(
            document_id=uuid4(),
            tenant_id=uuid4(),
            extraction_results={},
            validation_results={},
            insights=[],
        ))
        return processor

    @pytest.fixture
    def service(self, mock_processor):
        return BatchExtractionService(
            processor=mock_processor,
            document_fetcher=lambda doc_id: "Test document content",
        )

    @pytest.mark.asyncio
    async def test_create_job(self, service):
        """Test creating extraction job."""
        tenant_id = uuid4()
        doc_ids = [uuid4(), uuid4()]

        job = await service.create_job(
            tenant_id=tenant_id,
            document_ids=doc_ids,
        )

        assert job.tenant_id == tenant_id
        assert job.total_documents == 2
        assert job.status == JobStatus.QUEUED

    @pytest.mark.asyncio
    async def test_get_job_tenant_isolation(self, service):
        """Test tenant isolation when getting jobs."""
        tenant1 = uuid4()
        tenant2 = uuid4()

        job = await service.create_job(
            tenant_id=tenant1,
            document_ids=[uuid4()],
        )

        # Same tenant can access
        retrieved = await service.get_job(job.id, tenant1)
        assert retrieved is not None

        # Different tenant cannot
        retrieved = await service.get_job(job.id, tenant2)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_cancel_job(self, service):
        """Test job cancellation."""
        tenant_id = uuid4()
        job = await service.create_job(
            tenant_id=tenant_id,
            document_ids=[uuid4()],
        )

        success = await service.cancel_job(job.id, tenant_id)
        assert success is True

        cancelled = await service.get_job(job.id, tenant_id)
        assert cancelled.status == JobStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_list_jobs(self, service):
        """Test listing jobs."""
        tenant_id = uuid4()

        await service.create_job(tenant_id=tenant_id, document_ids=[uuid4()])
        await service.create_job(tenant_id=tenant_id, document_ids=[uuid4()])

        jobs = await service.list_jobs(tenant_id)
        assert len(jobs) == 2

    @pytest.mark.asyncio
    async def test_priority_handling(self, service):
        """Test jobs with different priorities."""
        tenant_id = uuid4()

        low = await service.create_job(
            tenant_id=tenant_id,
            document_ids=[uuid4()],
            priority=JobPriority.LOW,
        )
        high = await service.create_job(
            tenant_id=tenant_id,
            document_ids=[uuid4()],
            priority=JobPriority.HIGH,
        )

        assert high.priority > low.priority


class TestBatchExtractionWorker:
    @pytest.mark.asyncio
    async def test_worker_start_stop(self):
        """Test worker lifecycle."""
        mock_processor = MagicMock(spec=ExtractionProcessor)
        service = BatchExtractionService(processor=mock_processor)

        await service.start_worker()
        assert service._running is True

        await service.stop_worker()
        assert service._running is False
