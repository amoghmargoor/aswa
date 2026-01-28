"""Tests for extraction API endpoints."""

import pytest
from fastapi.testclient import TestClient
from uuid import uuid4

from tests.conftest import (
    TEST_TENANT_ID,
    TEST_USER_ID,
    TEST_DOCUMENT_ID,
    MockLLMClient,
)


class TestExtractionEndpoints:
    """Tests for extraction API endpoints."""

    def test_extract_requires_auth(self, test_client: TestClient) -> None:
        """Test that extraction requires tenant headers."""
        response = test_client.post(
            "/api/v1/extract",
            json={"document_ids": [str(uuid4())]},
        )

        assert response.status_code == 422  # Missing headers

    def test_extract_creates_job(
        self, test_client: TestClient, tenant_headers: dict[str, str]
    ) -> None:
        """Test creating an extraction job."""
        document_ids = [str(uuid4()), str(uuid4())]

        response = test_client.post(
            "/api/v1/extract",
            json={
                "document_ids": document_ids,
                "extraction_types": ["entities", "risks"],
                "force_reextract": False,
            },
            headers=tenant_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "job_id" in data["data"]
        assert data["data"]["status"] == "queued"
        assert data["data"]["documents_queued"] == 2

    def test_extract_with_priority(
        self, test_client: TestClient, tenant_headers: dict[str, str]
    ) -> None:
        """Test creating extraction job with priority."""
        response = test_client.post(
            "/api/v1/extract",
            json={
                "document_ids": [str(uuid4())],
                "priority": 5,
            },
            headers=tenant_headers,
        )

        assert response.status_code == 200

    def test_extract_invalid_document_ids(
        self, test_client: TestClient, tenant_headers: dict[str, str]
    ) -> None:
        """Test extraction with invalid document IDs."""
        response = test_client.post(
            "/api/v1/extract",
            json={
                "document_ids": ["not-a-uuid"],
            },
            headers=tenant_headers,
        )

        assert response.status_code == 422

    def test_extract_empty_documents(
        self, test_client: TestClient, tenant_headers: dict[str, str]
    ) -> None:
        """Test extraction with empty document list."""
        response = test_client.post(
            "/api/v1/extract",
            json={
                "document_ids": [],
            },
            headers=tenant_headers,
        )

        assert response.status_code == 422

    def test_get_job_status_not_found(
        self, test_client: TestClient, tenant_headers: dict[str, str]
    ) -> None:
        """Test getting status of non-existent job."""
        response = test_client.get(
            f"/api/v1/extract/{uuid4()}/status",
            headers=tenant_headers,
        )

        assert response.status_code == 404

    def test_cancel_job_not_found(
        self, test_client: TestClient, tenant_headers: dict[str, str]
    ) -> None:
        """Test cancelling non-existent job."""
        response = test_client.post(
            f"/api/v1/extract/{uuid4()}/cancel",
            headers=tenant_headers,
        )

        assert response.status_code == 404


class TestExtractionService:
    """Tests for ExtractionService."""

    @pytest.mark.asyncio
    async def test_create_extraction_job(
        self, mock_session_factory, mock_llm_client: MockLLMClient
    ) -> None:
        """Test creating extraction job."""
        from aswa_insight.services.extraction_service import ExtractionService

        service = ExtractionService(mock_session_factory, mock_llm_client)

        job = await service.create_extraction_job(
            document_ids=[uuid4(), uuid4()],
            tenant_id=TEST_TENANT_ID,
            extraction_types=["entities", "risks"],
            force_reextract=False,
            priority=0,
        )

        assert job.id is not None
        assert job.status == "queued"
        assert job.total_documents == 2
        assert len(job.extraction_types) == 2

    @pytest.mark.asyncio
    async def test_get_job_status(
        self, mock_session_factory, mock_llm_client: MockLLMClient
    ) -> None:
        """Test getting job status."""
        from aswa_insight.services.extraction_service import ExtractionService

        service = ExtractionService(mock_session_factory, mock_llm_client)

        # Create a job
        job = await service.create_extraction_job(
            document_ids=[uuid4()],
            tenant_id=TEST_TENANT_ID,
            extraction_types=["entities"],
        )

        # Get status
        status = await service.get_job_status(job.id, TEST_TENANT_ID)

        assert status is not None
        assert status["job_id"] == job.id
        assert status["status"] == "queued"
        assert status["total_documents"] == 1

    @pytest.mark.asyncio
    async def test_get_job_status_wrong_tenant(
        self, mock_session_factory, mock_llm_client: MockLLMClient
    ) -> None:
        """Test getting job status with wrong tenant."""
        from aswa_insight.services.extraction_service import ExtractionService

        service = ExtractionService(mock_session_factory, mock_llm_client)

        job = await service.create_extraction_job(
            document_ids=[uuid4()],
            tenant_id=TEST_TENANT_ID,
            extraction_types=["entities"],
        )

        # Try with different tenant
        status = await service.get_job_status(job.id, uuid4())

        assert status is None

    @pytest.mark.asyncio
    async def test_cancel_job(
        self, mock_session_factory, mock_llm_client: MockLLMClient
    ) -> None:
        """Test cancelling a job."""
        from aswa_insight.services.extraction_service import ExtractionService

        service = ExtractionService(mock_session_factory, mock_llm_client)

        job = await service.create_extraction_job(
            document_ids=[uuid4()],
            tenant_id=TEST_TENANT_ID,
            extraction_types=["entities"],
        )

        # Cancel
        success = await service.cancel_job(job.id, TEST_TENANT_ID)

        assert success is True

        # Check status
        status = await service.get_job_status(job.id, TEST_TENANT_ID)
        assert status["status"] == "cancelled"


class TestExtractionModels:
    """Tests for extraction Pydantic models."""

    def test_extracted_entity_validation(self) -> None:
        """Test ExtractedEntity model."""
        from aswa_insight.services.extraction_service import ExtractedEntity

        entity = ExtractedEntity(
            name="Acme Corp",
            entity_type="organization",
            description="A company",
            confidence=0.9,
            mentions=["Acme Corp is..."],
        )

        assert entity.name == "Acme Corp"
        assert entity.confidence == 0.9

    def test_extracted_entity_confidence_bounds(self) -> None:
        """Test confidence must be between 0 and 1."""
        from aswa_insight.services.extraction_service import ExtractedEntity

        with pytest.raises(ValueError):
            ExtractedEntity(
                name="Test",
                entity_type="test",
                description="test",
                confidence=1.5,  # Invalid
            )

    def test_extracted_risk_validation(self) -> None:
        """Test ExtractedRisk model."""
        from aswa_insight.services.extraction_service import ExtractedRisk

        risk = ExtractedRisk(
            title="Security Risk",
            description="Vulnerability found",
            category="security",
            severity="high",
            likelihood="possible",
            confidence=0.85,
        )

        assert risk.title == "Security Risk"
        assert risk.severity == "high"
