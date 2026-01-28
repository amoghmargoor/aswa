"""Integration tests for document processing flow."""

import pytest
import httpx
import asyncio
import os
from pathlib import Path

API_URL = os.environ.get("API_URL", "http://localhost:8000")


@pytest.fixture
def api_client():
    """Create API client."""
    return httpx.AsyncClient(base_url=API_URL, timeout=60.0)


@pytest.fixture
def auth_token():
    """Get authentication token."""
    # In a real test, this would authenticate properly
    return os.environ.get("TEST_API_TOKEN", "test-token")


@pytest.fixture
def sample_pdf(tmp_path):
    """Create a sample PDF file for testing."""
    # Create a simple text file (in real tests, use a proper PDF)
    file_path = tmp_path / "test-document.txt"
    file_path.write_text("""
    Test Document for ASWA Integration Tests

    This document contains sample content for testing the document
    processing pipeline. It includes:

    1. Risk Assessment
    The project has potential budget overrun risks of approximately
    15% based on current spending patterns.

    2. Opportunities
    There are opportunities for cost optimization in the
    procurement process that could save up to $50,000 annually.

    3. Recommendations
    We recommend implementing automated monitoring and
    establishing quarterly review processes.
    """)
    return file_path


class TestDocumentProcessingFlow:
    """Test the complete document processing flow."""

    @pytest.mark.asyncio
    async def test_upload_and_process_document(self, api_client, auth_token, sample_pdf):
        """Test uploading and processing a document."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        # Upload document
        with open(sample_pdf, "rb") as f:
            response = await api_client.post(
                "/api/v1/documents/upload",
                headers=headers,
                files={"file": ("test-document.txt", f, "text/plain")},
            )

        assert response.status_code == 201
        document = response.json()
        assert "id" in document
        document_id = document["id"]

        # Wait for processing
        max_retries = 30
        for _ in range(max_retries):
            response = await api_client.get(
                f"/api/v1/documents/{document_id}",
                headers=headers,
            )
            assert response.status_code == 200

            doc = response.json()
            if doc["status"] == "processed":
                break
            elif doc["status"] == "failed":
                pytest.fail(f"Document processing failed: {doc.get('error')}")

            await asyncio.sleep(2)
        else:
            pytest.fail("Document processing timed out")

        # Verify insights were generated
        response = await api_client.get(
            f"/api/v1/documents/{document_id}/insights",
            headers=headers,
        )
        assert response.status_code == 200
        insights = response.json()
        assert len(insights["items"]) > 0

    @pytest.mark.asyncio
    async def test_query_processed_document(self, api_client, auth_token, sample_pdf):
        """Test querying a processed document."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        # Upload and wait for processing
        with open(sample_pdf, "rb") as f:
            response = await api_client.post(
                "/api/v1/documents/upload",
                headers=headers,
                files={"file": ("test-document.txt", f, "text/plain")},
            )

        document_id = response.json()["id"]

        # Wait for processing
        await asyncio.sleep(10)

        # Query the document
        response = await api_client.post(
            "/api/v1/query",
            headers=headers,
            json={
                "query": "What risks are mentioned?",
                "document_ids": [document_id],
            },
        )

        assert response.status_code == 200
        result = response.json()
        assert "response" in result
        assert len(result["response"]) > 0


class TestAPIEndpoints:
    """Test API endpoint functionality."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, api_client):
        """Test health check endpoint."""
        response = await api_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_list_documents(self, api_client, auth_token):
        """Test listing documents."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        response = await api_client.get(
            "/api/v1/documents",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    @pytest.mark.asyncio
    async def test_list_insights(self, api_client, auth_token):
        """Test listing insights."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        response = await api_client.get(
            "/api/v1/insights",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    @pytest.mark.asyncio
    async def test_unauthorized_access(self, api_client):
        """Test that unauthorized access is rejected."""
        response = await api_client.get("/api/v1/documents")
        assert response.status_code == 401
