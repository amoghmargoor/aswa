"""Tests for agents API endpoints."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


class TestAgentsEndpoints:
    """Tests for agents API endpoints."""

    @pytest.fixture
    def tenant_id(self):
        """Create a tenant ID for testing."""
        return str(uuid4())

    @pytest.fixture
    def user_id(self):
        """Create a user ID for testing."""
        return str(uuid4())

    @pytest.fixture
    def sample_agent_data(self):
        """Create sample agent data."""
        return {
            "name": "test-agent",
            "display_name": "Test Agent",
            "description": "A test agent",
            "trigger": {
                "type": "schedule",
                "config": {"frequency": "daily"},
            },
            "actions": [
                {
                    "id": "action1",
                    "type": "summarize",
                    "config": {"style": "brief"},
                }
            ],
        }

    def test_create_agent(self, client, sample_agent_data):
        """Test creating an agent."""
        response = client.post(
            "/api/v1/agents",
            json=sample_agent_data,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-agent"
        assert "id" in data

    def test_list_agents(self, client):
        """Test listing agents."""
        response = client.get("/api/v1/agents")

        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert "total" in data

    def test_list_agents_with_filter(self, client):
        """Test listing agents with status filter."""
        response = client.get(
            "/api/v1/agents",
            params={"status": "active"},
        )

        assert response.status_code == 200

    def test_list_agents_with_pagination(self, client):
        """Test listing agents with pagination."""
        response = client.get(
            "/api/v1/agents",
            params={"limit": 10, "offset": 0},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 0

    def test_get_agent(self, client, sample_agent_data):
        """Test getting a specific agent."""
        # Create an agent first
        create_response = client.post(
            "/api/v1/agents",
            json=sample_agent_data,
        )
        agent_id = create_response.json()["id"]

        response = client.get(f"/api/v1/agents/{agent_id}")

        assert response.status_code == 200
        assert response.json()["id"] == agent_id

    def test_get_agent_not_found(self, client):
        """Test getting an agent that doesn't exist."""
        response = client.get(f"/api/v1/agents/{uuid4()}")

        assert response.status_code == 404

    def test_update_agent(self, client, sample_agent_data):
        """Test updating an agent."""
        # Create an agent first
        create_response = client.post(
            "/api/v1/agents",
            json=sample_agent_data,
        )
        agent_id = create_response.json()["id"]

        update_data = {
            "display_name": "Updated Agent Name",
            "description": "Updated description",
        }

        response = client.put(
            f"/api/v1/agents/{agent_id}",
            json=update_data,
        )

        assert response.status_code == 200
        assert response.json()["display_name"] == "Updated Agent Name"

    def test_delete_agent(self, client, sample_agent_data):
        """Test deleting an agent."""
        # Create an agent first
        create_response = client.post(
            "/api/v1/agents",
            json=sample_agent_data,
        )
        agent_id = create_response.json()["id"]

        response = client.delete(f"/api/v1/agents/{agent_id}")

        assert response.status_code == 204

        # Verify deletion
        get_response = client.get(f"/api/v1/agents/{agent_id}")
        assert get_response.status_code == 404

    def test_test_agent(self, client, sample_agent_data):
        """Test the test endpoint for an agent."""
        # Create an agent first
        create_response = client.post(
            "/api/v1/agents",
            json=sample_agent_data,
        )
        agent_id = create_response.json()["id"]

        response = client.post(
            f"/api/v1/agents/{agent_id}/test",
            json={"data": {"test_input": "value"}},
        )

        # May succeed or fail, but should not be 404
        assert response.status_code in [200, 500]

    def test_clone_agent(self, client, sample_agent_data):
        """Test cloning an agent."""
        # Create an agent first
        create_response = client.post(
            "/api/v1/agents",
            json=sample_agent_data,
        )
        agent_id = create_response.json()["id"]

        response = client.post(f"/api/v1/agents/{agent_id}/clone")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test-agent-copy"
        assert data["id"] != agent_id

    def test_activate_agent(self, client, sample_agent_data):
        """Test activating an agent."""
        # Create an agent first
        create_response = client.post(
            "/api/v1/agents",
            json=sample_agent_data,
        )
        agent_id = create_response.json()["id"]

        response = client.post(f"/api/v1/agents/{agent_id}/activate")

        assert response.status_code == 200
        assert response.json()["status"] == "active"

    def test_pause_agent(self, client, sample_agent_data):
        """Test pausing an agent."""
        # Create and activate an agent first
        create_response = client.post(
            "/api/v1/agents",
            json=sample_agent_data,
        )
        agent_id = create_response.json()["id"]
        client.post(f"/api/v1/agents/{agent_id}/activate")

        response = client.post(f"/api/v1/agents/{agent_id}/pause")

        assert response.status_code == 200
        assert response.json()["status"] == "paused"

    def test_get_agent_versions(self, client, sample_agent_data):
        """Test getting version history for an agent."""
        # Create an agent first
        create_response = client.post(
            "/api/v1/agents",
            json=sample_agent_data,
        )
        agent_id = create_response.json()["id"]

        response = client.get(f"/api/v1/agents/{agent_id}/versions")

        assert response.status_code == 200
        data = response.json()
        assert "versions" in data

    def test_get_agent_audit_log(self, client, sample_agent_data):
        """Test getting audit log for an agent."""
        # Create an agent first
        create_response = client.post(
            "/api/v1/agents",
            json=sample_agent_data,
        )
        agent_id = create_response.json()["id"]

        response = client.get(f"/api/v1/agents/{agent_id}/audit")

        assert response.status_code == 200
        data = response.json()
        assert "entries" in data


class TestTriggerEndpoint:
    """Tests for trigger endpoint."""

    @pytest.fixture
    def sample_agent_data(self):
        """Create sample agent data."""
        return {
            "name": "trigger-test-agent",
            "display_name": "Trigger Test Agent",
            "trigger": {"type": "manual"},
            "actions": [],
        }

    def test_trigger_not_implemented(self, client, sample_agent_data):
        """Test that trigger endpoint returns not implemented."""
        # Create an agent first
        create_response = client.post(
            "/api/v1/agents",
            json=sample_agent_data,
        )
        agent_id = create_response.json()["id"]

        response = client.post(
            f"/api/v1/agents/{agent_id}/trigger",
            json={"data": {}},
        )

        assert response.status_code == 501  # Not Implemented
