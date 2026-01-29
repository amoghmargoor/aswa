"""Tests for governance approval workflow."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from aswa_agents.governance import (
    AccessControl,
    ApprovalAction,
    ApprovalPolicy,
    ApprovalStatus,
    ApprovalWorkflow,
    Permission,
    PREDEFINED_ROLES,
    Role,
)


class TestApprovalWorkflow:
    """Tests for ApprovalWorkflow class."""

    @pytest.fixture
    def tenant_id(self):
        """Create a tenant ID for testing."""
        return uuid4()

    @pytest.fixture
    def workflow(self, tenant_id):
        """Create an approval workflow instance."""
        return ApprovalWorkflow(tenant_id)

    @pytest.fixture
    def sample_policy(self):
        """Create a sample approval policy."""
        return ApprovalPolicy(
            name="deploy-policy",
            description="Requires approval for deployment",
            action=ApprovalAction.DEPLOY,
            required_approvers=2,
            allowed_approver_roles=["admin", "approver"],
        )

    @pytest.mark.asyncio
    async def test_create_policy(self, workflow, sample_policy):
        """Test creating an approval policy."""
        created = await workflow.create_policy(sample_policy)

        assert created.id == sample_policy.id
        assert created.name == "deploy-policy"
        assert created.action == ApprovalAction.DEPLOY
        assert created.required_approvers == 2

    @pytest.mark.asyncio
    async def test_get_policies(self, workflow, sample_policy):
        """Test getting all policies."""
        await workflow.create_policy(sample_policy)

        policies = await workflow.get_policies()

        assert len(policies) >= 1
        assert any(p.name == "deploy-policy" for p in policies)

    @pytest.mark.asyncio
    async def test_request_approval(self, workflow, sample_policy):
        """Test requesting approval."""
        await workflow.create_policy(sample_policy)

        agent_id = uuid4()
        requester_id = uuid4()

        request = await workflow.request_approval(
            agent_id=agent_id,
            action=ApprovalAction.DEPLOY,
            requester_id=requester_id,
            details={"version": "1.0.0"},
        )

        assert request.agent_id == agent_id
        assert request.action == ApprovalAction.DEPLOY
        assert request.status == ApprovalStatus.PENDING
        assert request.requester_id == requester_id
        assert request.required_approvers == 2

    @pytest.mark.asyncio
    async def test_approve_request(self, workflow, sample_policy):
        """Test approving a request."""
        await workflow.create_policy(sample_policy)

        request = await workflow.request_approval(
            agent_id=uuid4(),
            action=ApprovalAction.DEPLOY,
            requester_id=uuid4(),
            details={},
        )

        approver1 = uuid4()
        updated = await workflow.approve(request.id, approver1, "Looks good")

        assert updated.status == ApprovalStatus.PENDING  # Still needs 1 more
        assert len(updated.approvals) == 1
        assert updated.approvals[0].approver_id == approver1

        approver2 = uuid4()
        updated = await workflow.approve(request.id, approver2, "Approved")

        assert updated.status == ApprovalStatus.APPROVED
        assert len(updated.approvals) == 2

    @pytest.mark.asyncio
    async def test_reject_request(self, workflow, sample_policy):
        """Test rejecting a request."""
        await workflow.create_policy(sample_policy)

        request = await workflow.request_approval(
            agent_id=uuid4(),
            action=ApprovalAction.DEPLOY,
            requester_id=uuid4(),
            details={},
        )

        rejector = uuid4()
        updated = await workflow.reject(request.id, rejector, "Not ready")

        assert updated.status == ApprovalStatus.REJECTED
        assert updated.rejection_reason == "Not ready"
        assert updated.rejected_by == rejector

    @pytest.mark.asyncio
    async def test_get_pending_for_user(self, workflow, sample_policy):
        """Test getting pending approvals for a user."""
        await workflow.create_policy(sample_policy)

        # Create multiple requests
        for _ in range(3):
            await workflow.request_approval(
                agent_id=uuid4(),
                action=ApprovalAction.DEPLOY,
                requester_id=uuid4(),
                details={},
            )

        user_id = uuid4()
        pending = await workflow.get_pending_for_user(user_id)

        assert len(pending) == 3
        assert all(p.status == ApprovalStatus.PENDING for p in pending)


class TestAccessControl:
    """Tests for AccessControl class."""

    @pytest.fixture
    def tenant_id(self):
        """Create a tenant ID for testing."""
        return uuid4()

    @pytest.fixture
    def access_control(self, tenant_id):
        """Create an access control instance."""
        return AccessControl(tenant_id)

    def test_predefined_roles_loaded(self, access_control):
        """Test that predefined roles are loaded."""
        assert len(PREDEFINED_ROLES) > 0

    @pytest.mark.asyncio
    async def test_get_roles(self, access_control):
        """Test getting all roles."""
        roles = await access_control.get_roles()

        assert len(roles) >= len(PREDEFINED_ROLES)

    @pytest.mark.asyncio
    async def test_create_custom_role(self, access_control):
        """Test creating a custom role."""
        role = Role(
            name="custom-approver",
            display_name="Custom Approver",
            description="Can approve agents",
            permissions=[Permission.AGENT_VIEW, Permission.AGENT_APPROVE],
            is_system=False,
        )

        created = await access_control.create_role(role)

        assert created.name == "custom-approver"
        assert Permission.AGENT_APPROVE in created.permissions
        assert not created.is_system

    @pytest.mark.asyncio
    async def test_assign_role(self, access_control):
        """Test assigning a role to a user."""
        roles = await access_control.get_roles()
        admin_role = next(r for r in roles if r.name == "admin")

        user_id = uuid4()
        await access_control.assign_role(user_id, admin_role.id)

        user_roles = await access_control.get_user_roles(user_id)
        assert any(r.id == admin_role.id for r in user_roles)

    @pytest.mark.asyncio
    async def test_check_permission_granted(self, access_control):
        """Test checking permission when granted."""
        roles = await access_control.get_roles()
        admin_role = next(r for r in roles if r.name == "admin")

        user_id = uuid4()
        await access_control.assign_role(user_id, admin_role.id)

        has_permission = await access_control.check_permission(
            user_id=user_id,
            permission=Permission.AGENT_CREATE,
        )

        assert has_permission is True

    @pytest.mark.asyncio
    async def test_check_permission_denied(self, access_control):
        """Test checking permission when denied."""
        user_id = uuid4()  # User with no roles

        has_permission = await access_control.check_permission(
            user_id=user_id,
            permission=Permission.AGENT_DELETE,
        )

        assert has_permission is False

    @pytest.mark.asyncio
    async def test_get_user_permissions(self, access_control):
        """Test getting all permissions for a user."""
        roles = await access_control.get_roles()
        viewer_role = next(r for r in roles if r.name == "viewer")

        user_id = uuid4()
        await access_control.assign_role(user_id, viewer_role.id)

        permissions = await access_control.get_user_permissions(user_id)

        assert Permission.AGENT_VIEW in permissions
        assert Permission.AGENT_DELETE not in permissions

    @pytest.mark.asyncio
    async def test_remove_role(self, access_control):
        """Test removing a role from a user."""
        roles = await access_control.get_roles()
        admin_role = next(r for r in roles if r.name == "admin")

        user_id = uuid4()
        await access_control.assign_role(user_id, admin_role.id)
        await access_control.remove_role(user_id, admin_role.id)

        user_roles = await access_control.get_user_roles(user_id)
        assert not any(r.id == admin_role.id for r in user_roles)
