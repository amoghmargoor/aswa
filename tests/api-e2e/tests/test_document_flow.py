import pytest
import httpx
import os
import time
from pathlib import Path

API_URL = os.environ.get("API_URL", "http://localhost:8000")


class TestDocumentFlow:
    """Test complete document processing flow."""

    @pytest.fixture
    def auth_headers(self):
        """Get authentication headers."""
        token = os.environ.get("API_TOKEN")
        return {"Authorization": f"Bearer {token}"}

    @pytest.fixture
    def test_file(self, tmp_path):
        """Create a test file."""
        file_path = tmp_path / "test-document.txt"
        file_path.write_text("""
        This is a test document for ASWA.

        It contains some sample text about various topics:

        1. Risk Assessment
        The project has several identified risks including budget overruns,
        timeline delays, and resource constraints.

        2. Opportunities
        There are opportunities for cost savings through automation
        and improved efficiency in the workflow.

        3. Recommendations
        We recommend implementing automated monitoring and establishing
        clear communication channels.
        """)
        return file_path

    def test_upload_document(self, auth_headers, test_file):
        """Test document upload."""
        with open(test_file, "rb") as f:
            response = httpx.post(
                f"{API_URL}/api/v1/documents/upload",
                headers=auth_headers,
                files={"file": ("test-document.txt", f, "text/plain")},
                timeout=60.0,
            )

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["name"] == "test-document.txt"
        assert data["status"] == "pending"

        return data["id"]

    def test_document_processing(self, auth_headers, test_file):
        """Test document processing completes."""
        # Upload document
        with open(test_file, "rb") as f:
            response = httpx.post(
                f"{API_URL}/api/v1/documents/upload",
                headers=auth_headers,
                files={"file": ("test-document.txt", f, "text/plain")},
                timeout=60.0,
            )

        document_id = response.json()["id"]

        # Wait for processing to complete
        max_wait = 120
        start = time.time()

        while time.time() - start < max_wait:
            response = httpx.get(
                f"{API_URL}/api/v1/documents/{document_id}",
                headers=auth_headers,
            )

            data = response.json()
            if data["status"] == "processed":
                break
            elif data["status"] == "failed":
                pytest.fail(f"Document processing failed: {data.get('error')}")

            time.sleep(5)
        else:
            pytest.fail("Document processing timed out")

        assert data["status"] == "processed"
        assert data["insight_count"] > 0

    def test_get_document_insights(self, auth_headers, test_file):
        """Test getting insights from a document."""
        # Upload and wait for processing
        with open(test_file, "rb") as f:
            response = httpx.post(
                f"{API_URL}/api/v1/documents/upload",
                headers=auth_headers,
                files={"file": ("test-document.txt", f, "text/plain")},
                timeout=60.0,
            )

        document_id = response.json()["id"]

        # Wait for processing
        time.sleep(30)

        # Get insights
        response = httpx.get(
            f"{API_URL}/api/v1/documents/{document_id}/insights",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["items"], list)

        # Check insight structure
        if len(data["items"]) > 0:
            insight = data["items"][0]
            assert "id" in insight
            assert "type" in insight
            assert "title" in insight
            assert "confidence" in insight

    def test_query_document(self, auth_headers, test_file):
        """Test querying about a specific document."""
        # Upload and wait for processing
        with open(test_file, "rb") as f:
            response = httpx.post(
                f"{API_URL}/api/v1/documents/upload",
                headers=auth_headers,
                files={"file": ("test-document.txt", f, "text/plain")},
                timeout=60.0,
            )

        document_id = response.json()["id"]

        # Wait for processing
        time.sleep(30)

        # Query about the document
        response = httpx.post(
            f"{API_URL}/api/v1/query",
            headers=auth_headers,
            json={
                "query": "What risks are mentioned in the document?",
                "document_ids": [document_id],
            },
            timeout=120.0,
        )

        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "risk" in data["response"].lower() or "budget" in data["response"].lower()

    def test_delete_document(self, auth_headers, test_file):
        """Test document deletion."""
        # Upload document
        with open(test_file, "rb") as f:
            response = httpx.post(
                f"{API_URL}/api/v1/documents/upload",
                headers=auth_headers,
                files={"file": ("test-document.txt", f, "text/plain")},
                timeout=60.0,
            )

        document_id = response.json()["id"]

        # Delete document
        response = httpx.delete(
            f"{API_URL}/api/v1/documents/{document_id}",
            headers=auth_headers,
        )

        assert response.status_code == 204

        # Verify document is deleted
        response = httpx.get(
            f"{API_URL}/api/v1/documents/{document_id}",
            headers=auth_headers,
        )

        assert response.status_code == 404
