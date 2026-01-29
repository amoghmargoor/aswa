"""Tests for approvals API endpoints."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from aswa_agents.governance import ApprovalAction, Permission


class TestApprovalsEndpoints:
    """Tests for approvals API endpoints."""

    @pytest.fixture
    def tenant_id(self):
        """Create a tenant ID for testing."""
        return str(uuid4())

    @pytest.fixture
    def user_id(self):
        """Create a user ID for testing."""
        return str(uuid4())

    def test_list_pending_approvals(self, client, user_id):
        """Test listing pending approvals."""
        response = client.get(
            "/api/v1/approvals",
            params={"user_id": user_id},
        )

        assert response.status_code == 200
        data = response.json()
        assert "approvals" in data
        assert "total" in data

    def test_list_approvals_with_status_filter(self, client, user_id):
        """Test listing approvals with status filter."""
        response = client.get(
            "/api/v1/approvals",
            params={"user_id": user_id, "status": "pending"},
        )

        assert response.status_code == 200

    def test_get_approval_not_found(self, client):
        """Test getting an approval that doesn't exist."""
        response = client.get(f"/api/v1/approvals/{uuid4()}")

        assert response.status_code == 404

    def test_approve_not_found(self, client, user_id):
        """Test approving a non-existent request."""
        response = client.post(
            f"/api/v1/approvals/{uuid4()}/approve",
            params={"user_id": user_id},
        )

        assert response.status_code in [400, 404]

    def test_reject_not_found(self, client, user_id):
        """Test rejecting a non-existent request."""
        response = client.post(
            f"/api/v1/approvals/{uuid4()}/reject",
            params={"user_id": user_id, "reason": "Not valid"},
        )

        assert response.status_code in [400, 404]

    def test_list_policies(self, client):
        """Test listing approval policies."""
        response = client.get("/api/v1/approvals/policies")

        assert response.status_code == 200
        data = response.json()
        assert "policies" in data

    def test_create_policy(self, client):
        """Test creating an approval policy."""
        policy_data = {
            "name": "test-policy",
            "description": "Test policy",
            "action": ApprovalAction.DEPLOY.value,
            "required_approvers": 1,
            "allowed_approver_roles": ["admin"],
        }

        response = client.post(
            "/api/v1/approvals/policies",
            json=policy_data,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-policy"

    def test_delete_policy_not_found(self, client):
        """Test deleting a policy that doesn't exist."""
        response = client.delete(f"/api/v1/approvals/policies/{uuid4()}")

        assert response.status_code == 404

    def test_list_roles(self, client):
        """Test listing roles."""
        response = client.get("/api/v1/approvals/roles")

        assert response.status_code == 200
        data = response.json()
        assert "roles" in data
        assert len(data["roles"]) > 0  # Should have predefined roles

    def test_create_role(self, client):
        """Test creating a custom role."""
        role_data = {
            "name": "custom-role",
            "display_name": "Custom Role",
            "description": "A custom role",
            "permissions": [Permission.AGENT_VIEW.value, Permission.AGENT_CREATE.value],
        }

        response = client.post(
            "/api/v1/approvals/roles",
            json=role_data,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "custom-role"

    def test_get_user_permissions(self, client, user_id):
        """Test getting user permissions."""
        response = client.get(f"/api/v1/approvals/users/{user_id}/permissions")

        assert response.status_code == 200
        data = response.json()
        assert "user_id" in data
        assert "permissions" in data

    def test_assign_role(self, client, user_id):
        """Test assigning a role to a user."""
        # First get a role
        roles_response = client.get("/api/v1/approvals/roles")
        roles = roles_response.json()["roles"]

        if roles:
            role_id = roles[0]["id"]
            response = client.post(
                f"/api/v1/approvals/users/{user_id}/roles/{role_id}"
            )

            assert response.status_code == 200

    def test_check_permission(self, client, user_id):
        """Test checking a permission."""
        response = client.get(
            "/api/v1/approvals/check",
            params={
                "user_id": user_id,
                "permission": Permission.AGENT_VIEW.value,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "allowed" in data
