"""Agent governance - approval workflows and RBAC."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
import structlog

logger = structlog.get_logger()


class ApprovalStatus(str, Enum):
    """Status of an approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ApprovalAction(str, Enum):
    """Actions that require approval."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    ACTIVATE = "activate"
    DEPLOY = "deploy"
    EXECUTE = "execute"


class Permission(str, Enum):
    """Permissions for agent operations."""

    AGENT_VIEW = "agent:view"
    AGENT_CREATE = "agent:create"
    AGENT_EDIT = "agent:edit"
    AGENT_DELETE = "agent:delete"
    AGENT_ACTIVATE = "agent:activate"
    AGENT_EXECUTE = "agent:execute"
    AGENT_APPROVE = "agent:approve"
    AGENT_AUDIT = "agent:audit"
    TEMPLATE_VIEW = "template:view"
    TEMPLATE_CREATE = "template:create"
    TEMPLATE_EDIT = "template:edit"


class Role(BaseModel):
    """A role with associated permissions."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    display_name: str = ""
    description: str = ""
    permissions: list[Permission] = Field(default_factory=list)
    is_system: bool = False


# Predefined roles
PREDEFINED_ROLES = [
    Role(
        id=uuid4(),
        name="viewer",
        display_name="Viewer",
        description="Can view agents and their status",
        permissions=[Permission.AGENT_VIEW, Permission.TEMPLATE_VIEW],
        is_system=True,
    ),
    Role(
        id=uuid4(),
        name="operator",
        display_name="Operator",
        description="Can create and manage agents",
        permissions=[
            Permission.AGENT_VIEW,
            Permission.AGENT_CREATE,
            Permission.AGENT_EDIT,
            Permission.AGENT_EXECUTE,
            Permission.TEMPLATE_VIEW,
        ],
        is_system=True,
    ),
    Role(
        id=uuid4(),
        name="approver",
        display_name="Approver",
        description="Can approve agent changes",
        permissions=[
            Permission.AGENT_VIEW,
            Permission.AGENT_APPROVE,
            Permission.TEMPLATE_VIEW,
        ],
        is_system=True,
    ),
    Role(
        id=uuid4(),
        name="admin",
        display_name="Administrator",
        description="Full access to all agent features",
        permissions=list(Permission),
        is_system=True,
    ),
]


class Approval(BaseModel):
    """A single approval record."""

    id: UUID = Field(default_factory=uuid4)
    approver_id: UUID
    comment: str = ""
    approved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ApprovalRequest(BaseModel):
    """A request for approval."""

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID | None = None
    agent_id: UUID
    action: ApprovalAction
    status: ApprovalStatus = ApprovalStatus.PENDING
    requester_id: UUID
    details: dict[str, Any] = Field(default_factory=dict)
    required_approvers: int = 1
    approvals: list[Approval] = Field(default_factory=list)
    rejection_reason: str | None = None
    rejected_by: UUID | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None


class ApprovalPolicy(BaseModel):
    """Policy defining what requires approval."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    description: str = ""
    action: ApprovalAction
    required_approvers: int = 1
    allowed_approver_roles: list[str] = Field(default_factory=list)
    auto_approve_conditions: dict[str, Any] | None = None
    is_active: bool = True
    timeout_hours: int = 24


class ApprovalWorkflow:
    """Manages approval workflows."""

    def __init__(self, tenant_id: UUID):
        self.tenant_id = tenant_id
        self._policies: dict[UUID, ApprovalPolicy] = {}
        self._requests: dict[UUID, ApprovalRequest] = {}
        self._logger = logger.bind(
            component="ApprovalWorkflow",
            tenant_id=str(tenant_id),
        )

    async def get_policies(self) -> list[ApprovalPolicy]:
        """Get all approval policies."""
        return list(self._policies.values())

    async def create_policy(self, policy: ApprovalPolicy) -> ApprovalPolicy:
        """Create an approval policy."""
        self._policies[policy.id] = policy
        self._logger.info(
            "Policy created",
            policy_id=str(policy.id),
            policy_name=policy.name,
        )
        return policy

    async def delete_policy(self, policy_id: UUID) -> None:
        """Delete an approval policy."""
        if policy_id not in self._policies:
            raise ValueError(f"Policy {policy_id} not found")
        del self._policies[policy_id]
        self._logger.info("Policy deleted", policy_id=str(policy_id))

    async def get_request(self, request_id: UUID) -> ApprovalRequest | None:
        """Get an approval request by ID."""
        return self._requests.get(request_id)

    async def request_approval(
        self,
        agent_id: UUID,
        action: ApprovalAction,
        requester_id: UUID,
        details: dict[str, Any] | None = None,
    ) -> ApprovalRequest:
        """Create an approval request."""
        from datetime import timedelta

        # Find matching policy
        required_approvers = 1
        expires_at = None
        for policy in self._policies.values():
            if policy.action == action and policy.is_active:
                required_approvers = policy.required_approvers
                if policy.timeout_hours:
                    expires_at = datetime.now(timezone.utc) + timedelta(hours=policy.timeout_hours)
                break

        request = ApprovalRequest(
            tenant_id=self.tenant_id,
            agent_id=agent_id,
            action=action,
            requester_id=requester_id,
            details=details or {},
            required_approvers=required_approvers,
            expires_at=expires_at,
        )

        self._requests[request.id] = request

        self._logger.info(
            "Approval requested",
            request_id=str(request.id),
            action=action.value,
            agent_id=str(agent_id),
        )

        return request

    async def approve(
        self,
        request_id: UUID,
        approver_id: UUID,
        comment: str = "",
    ) -> ApprovalRequest:
        """Approve a request."""
        request = self._requests.get(request_id)
        if not request:
            raise ValueError(f"Request {request_id} not found")

        if request.status != ApprovalStatus.PENDING:
            raise ValueError(f"Request is not pending: {request.status}")

        # Add approval
        approval = Approval(
            approver_id=approver_id,
            comment=comment,
        )
        request.approvals.append(approval)

        # Check if enough approvals
        if len(request.approvals) >= request.required_approvers:
            request.status = ApprovalStatus.APPROVED

        self._logger.info(
            "Request approved",
            request_id=str(request_id),
            approver_id=str(approver_id),
            is_complete=request.status == ApprovalStatus.APPROVED,
        )

        return request

    async def reject(
        self,
        request_id: UUID,
        rejector_id: UUID,
        reason: str,
    ) -> ApprovalRequest:
        """Reject a request."""
        request = self._requests.get(request_id)
        if not request:
            raise ValueError(f"Request {request_id} not found")

        if request.status != ApprovalStatus.PENDING:
            raise ValueError(f"Request is not pending: {request.status}")

        request.status = ApprovalStatus.REJECTED
        request.rejected_by = rejector_id
        request.rejection_reason = reason

        self._logger.info(
            "Request rejected",
            request_id=str(request_id),
            rejector_id=str(rejector_id),
        )

        return request

    async def get_pending_for_user(self, user_id: UUID) -> list[ApprovalRequest]:
        """Get pending approval requests for a user."""
        # Return all pending requests (in a real impl, filter by approver eligibility)
        return [r for r in self._requests.values() if r.status == ApprovalStatus.PENDING]


class AccessControl:
    """Role-based access control for agents."""

    def __init__(self, tenant_id: UUID):
        self.tenant_id = tenant_id
        self._user_roles: dict[UUID, list[UUID]] = {}
        self._custom_roles: dict[UUID, Role] = {}
        self._roles_by_name: dict[str, Role] = {}
        self._logger = logger.bind(
            component="AccessControl",
            tenant_id=str(tenant_id),
        )

        # Index predefined roles by name
        for role in PREDEFINED_ROLES:
            self._roles_by_name[role.name] = role

    async def get_roles(self) -> list[Role]:
        """Get all roles."""
        return PREDEFINED_ROLES + list(self._custom_roles.values())

    async def create_role(self, role: Role) -> Role:
        """Create a custom role."""
        if role.name in self._roles_by_name:
            raise ValueError(f"Role name already exists: {role.name}")
        role.is_system = False
        self._custom_roles[role.id] = role
        self._roles_by_name[role.name] = role
        self._logger.info("Role created", role_id=str(role.id), role_name=role.name)
        return role

    def _get_role_by_id(self, role_id: UUID) -> Role | None:
        """Get a role by ID."""
        for role in PREDEFINED_ROLES:
            if role.id == role_id:
                return role
        return self._custom_roles.get(role_id)

    async def get_user_roles(self, user_id: UUID) -> list[Role]:
        """Get all roles for a user."""
        role_ids = self._user_roles.get(user_id, [])
        roles = []
        for role_id in role_ids:
            role = self._get_role_by_id(role_id)
            if role:
                roles.append(role)
        return roles

    async def assign_role(self, user_id: UUID, role_id: UUID) -> None:
        """Assign a role to a user."""
        role = self._get_role_by_id(role_id)
        if not role:
            raise ValueError(f"Role {role_id} not found")

        if user_id not in self._user_roles:
            self._user_roles[user_id] = []
        if role_id not in self._user_roles[user_id]:
            self._user_roles[user_id].append(role_id)
            self._logger.info(
                "Role assigned",
                user_id=str(user_id),
                role_id=str(role_id),
            )

    async def remove_role(self, user_id: UUID, role_id: UUID) -> None:
        """Remove a role from a user."""
        if user_id in self._user_roles:
            self._user_roles[user_id] = [
                r for r in self._user_roles[user_id] if r != role_id
            ]
            self._logger.info(
                "Role removed",
                user_id=str(user_id),
                role_id=str(role_id),
            )

    async def get_user_permissions(self, user_id: UUID) -> set[Permission]:
        """Get all permissions for a user."""
        permissions: set[Permission] = set()
        roles = await self.get_user_roles(user_id)
        for role in roles:
            permissions.update(role.permissions)
        return permissions

    async def check_permission(
        self,
        user_id: UUID,
        permission: Permission,
        resource_id: UUID | None = None,
    ) -> bool:
        """Check if user has a specific permission."""
        permissions = await self.get_user_permissions(user_id)
        return permission in permissions
