"""Tests for actions API endpoints."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from aswa_agents.actions.blocks import ActionCategory


class TestActionsEndpoints:
    """Tests for actions API endpoints."""

    @pytest.fixture
    def tenant_id(self):
        """Create a tenant ID for testing."""
        return str(uuid4())

    def test_list_action_blocks(self, client):
        """Test listing action blocks."""
        response = client.get("/api/v1/actions")

        assert response.status_code == 200
        data = response.json()
        assert "blocks" in data
        assert "total" in data
        assert isinstance(data["blocks"], list)

    def test_list_action_blocks_by_category(self, client):
        """Test filtering action blocks by category."""
        response = client.get(
            "/api/v1/actions",
            params={"category": ActionCategory.DATA.value},
        )

        assert response.status_code == 200
        data = response.json()
        assert all(
            b["category"] == ActionCategory.DATA.value
            for b in data["blocks"]
        )

    def test_list_categories(self, client):
        """Test listing action categories."""
        response = client.get("/api/v1/actions/categories")

        assert response.status_code == 200
        data = response.json()
        assert "categories" in data
        assert len(data["categories"]) > 0

        # Check category structure
        for cat in data["categories"]:
            assert "id" in cat
            assert "name" in cat
            assert "description" in cat

    def test_get_action_block(self, client):
        """Test getting a specific action block."""
        # First list to get a block ID
        list_response = client.get("/api/v1/actions")
        blocks = list_response.json()["blocks"]

        if blocks:
            block_id = blocks[0]["id"]
            response = client.get(f"/api/v1/actions/{block_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == block_id

    def test_get_action_block_not_found(self, client):
        """Test getting an action block that doesn't exist."""
        response = client.get("/api/v1/actions/nonexistent-block")

        assert response.status_code == 404

    def test_get_action_block_schema(self, client):
        """Test getting action block schema."""
        list_response = client.get("/api/v1/actions")
        blocks = list_response.json()["blocks"]

        if blocks:
            block_id = blocks[0]["id"]
            response = client.get(f"/api/v1/actions/{block_id}/schema")

            assert response.status_code == 200
            data = response.json()
            assert "id" in data
            assert "input_schema" in data
            assert "output_schema" in data
            assert "config_schema" in data

    def test_get_schema_not_found(self, client):
        """Test getting schema for non-existent block."""
        response = client.get("/api/v1/actions/nonexistent/schema")

        assert response.status_code == 404

    def test_validate_action_config_valid(self, client):
        """Test validating valid action config."""
        list_response = client.get("/api/v1/actions")
        blocks = list_response.json()["blocks"]

        if blocks:
            block_id = blocks[0]["id"]
            response = client.post(
                f"/api/v1/actions/{block_id}/validate",
                json={"some_config": "value"},
            )

            assert response.status_code == 200
            data = response.json()
            assert "valid" in data
            assert "errors" in data

    def test_validate_config_not_found(self, client):
        """Test validating config for non-existent block."""
        response = client.post(
            "/api/v1/actions/nonexistent/validate",
            json={"config": "value"},
        )

        assert response.status_code == 404

    def test_preview_action_execution(self, client):
        """Test previewing action execution."""
        list_response = client.get("/api/v1/actions")
        blocks = list_response.json()["blocks"]

        if blocks:
            block_id = blocks[0]["id"]
            response = client.post(
                f"/api/v1/actions/{block_id}/preview",
                json={
                    "config": {"key": "value"},
                    "sample_input": {"data": "test"},
                },
            )

            # May succeed or fail depending on config validation
            assert response.status_code in [200, 400]

    def test_preview_not_found(self, client):
        """Test preview for non-existent block."""
        response = client.post(
            "/api/v1/actions/nonexistent/preview",
            json={"config": {}},
        )

        assert response.status_code == 404


class TestActionBlockResponse:
    """Tests for action block response structure."""

    def test_block_response_fields(self, client):
        """Test that block responses have required fields."""
        response = client.get("/api/v1/actions")
        blocks = response.json()["blocks"]

        for block in blocks:
            assert "id" in block
            assert "name" in block
            assert "display_name" in block
            assert "description" in block
            assert "category" in block
            assert "icon" in block
            assert "version" in block

    def test_schema_response_fields(self, client):
        """Test that schema responses have required fields."""
        list_response = client.get("/api/v1/actions")
        blocks = list_response.json()["blocks"]

        if blocks:
            block_id = blocks[0]["id"]
            response = client.get(f"/api/v1/actions/{block_id}/schema")
            data = response.json()

            assert "id" in data
            assert "name" in data
            assert isinstance(data["input_schema"], dict)
            assert isinstance(data["output_schema"], dict)
            assert isinstance(data["config_schema"], dict)
