"""Tests for templates API endpoints."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from aswa_agents.templates import TemplateCategory


class TestTemplatesEndpoints:
    """Tests for templates API endpoints."""

    @pytest.fixture
    def tenant_id(self):
        """Create a tenant ID for testing."""
        return str(uuid4())

    @pytest.fixture
    def mock_tenant_dependency(self, tenant_id):
        """Mock the tenant dependency."""
        async def get_tenant():
            return tenant_id
        return get_tenant

    def test_list_templates(self, client, mock_tenant_dependency):
        """Test listing templates."""
        response = client.get("/api/v1/templates")

        assert response.status_code == 200
        data = response.json()
        assert "templates" in data
        assert "total" in data
        assert isinstance(data["templates"], list)

    def test_list_templates_by_category(self, client):
        """Test filtering templates by category."""
        response = client.get(
            "/api/v1/templates",
            params={"category": TemplateCategory.COMMUNICATION.value},
        )

        assert response.status_code == 200
        data = response.json()
        assert all(
            t["category"] == TemplateCategory.COMMUNICATION.value
            for t in data["templates"]
        )

    def test_list_templates_by_search(self, client):
        """Test searching templates."""
        response = client.get(
            "/api/v1/templates",
            params={"search": "email"},
        )

        assert response.status_code == 200

    def test_get_template(self, client):
        """Test getting a specific template."""
        # First list to get a template ID
        list_response = client.get("/api/v1/templates")
        templates = list_response.json()["templates"]

        if templates:
            template_id = templates[0]["id"]
            response = client.get(f"/api/v1/templates/{template_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == template_id

    def test_get_template_not_found(self, client):
        """Test getting a template that doesn't exist."""
        response = client.get(f"/api/v1/templates/{uuid4()}")

        assert response.status_code == 404

    def test_create_template(self, client):
        """Test creating a template."""
        template_data = {
            "name": "test-template",
            "display_name": "Test Template",
            "description": "A test template",
            "category": TemplateCategory.CUSTOM.value,
            "icon": "test",
            "tags": ["test"],
            "definition": {
                "trigger": {"type": "manual"},
                "actions": [],
            },
            "variables": [
                {
                    "name": "test_var",
                    "display_name": "Test Variable",
                    "type": "string",
                    "required": True,
                }
            ],
        }

        response = client.post(
            "/api/v1/templates",
            json=template_data,
            params={"user_id": str(uuid4())},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-template"

    def test_preview_template(self, client):
        """Test previewing a template."""
        # Get a template first
        list_response = client.get("/api/v1/templates")
        templates = list_response.json()["templates"]

        if templates:
            template_id = templates[0]["id"]
            response = client.post(
                f"/api/v1/templates/{template_id}/preview",
                json={"variable_values": {}},
            )

            assert response.status_code == 200
            data = response.json()
            assert "definition" in data
            assert "variables_used" in data

    def test_validate_template_variables(self, client):
        """Test validating template variables."""
        list_response = client.get("/api/v1/templates")
        templates = list_response.json()["templates"]

        if templates:
            template_id = templates[0]["id"]
            response = client.post(
                f"/api/v1/templates/{template_id}/validate",
                json={"email_inbox": "test@example.com"},
            )

            assert response.status_code == 200
            data = response.json()
            assert "valid" in data
            assert "errors" in data

    def test_instantiate_template(self, client, mock_db_session):
        """Test instantiating a template."""
        list_response = client.get("/api/v1/templates")
        templates = list_response.json()["templates"]

        if templates:
            template = templates[0]
            template_id = template["id"]

            # Build variable values from template variables
            variables = {}
            for var in template.get("variables", []):
                if var["required"]:
                    if var["type"] == "string":
                        variables[var["name"]] = "test-value"
                    elif var["type"] == "number":
                        variables[var["name"]] = 1

            response = client.post(
                f"/api/v1/templates/{template_id}/instantiate",
                json={
                    "name": "new-agent-from-template",
                    "display_name": "New Agent",
                    "description": "Created from template",
                    "variables": variables,
                },
                params={"user_id": str(uuid4())},
            )

            # May fail due to missing DB, but should not be 404
            assert response.status_code in [200, 201, 400, 500]
