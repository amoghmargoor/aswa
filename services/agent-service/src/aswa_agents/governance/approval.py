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

    CREATE_AGENT = "create_agent"
    UPDATE_AGENT = "update_agent"
    DELETE_AGENT = "delete_agent"
    ACTIVATE_AGENT = "activate_agent"
    EXECUTE_AGENT = "execute_agent"


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

    id: str
    name: str
    description: str = ""
    permissions: list[Permission] = Field(default_factory=list)
    is_system: bool = False


# Predefined roles
PREDEFINED_ROLES = {
    "viewer": Role(
        id="viewer",
        name="Viewer",
        description="Can view agents and their status",
        permissions=[Permission.AGENT_VIEW, Permission.TEMPLATE_VIEW],
        is_system=True,
    ),
    "operator": Role(
        id="operator",
        name="Operator",
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
    "approver": Role(
        id="approver",
        name="Approver",
        description="Can approve agent changes",
        permissions=[
            Permission.AGENT_VIEW,
            Permission.AGENT_APPROVE,
            Permission.TEMPLATE_VIEW,
        ],
        is_system=True,
    ),
    "admin": Role(
        id="admin",
        name="Administrator",
        description="Full access to all agent features",
        permissions=list(Permission),
        is_system=True,
    ),
}


class ApprovalRequest(BaseModel):
    """A request for approval."""

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    action: ApprovalAction
    resource_id: UUID
    resource_type: str = "agent"
    requested_by: UUID
    status: ApprovalStatus = ApprovalStatus.PENDING
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
    review_comment: str | None = None


class ApprovalPolicy(BaseModel):
    """Policy defining what requires approval."""

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    name: str
    description: str = ""
    enabled: bool = True
    actions: list[ApprovalAction] = Field(default_factory=list)
    conditions: dict[str, Any] = Field(default_factory=dict)
    required_approvers: int = 1
    approver_roles: list[str] = Field(default_factory=lambda: ["approver", "admin"])
    timeout_hours: int = 24
    auto_approve_confidence: float | None = None  # Auto-approve if confidence above threshold


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

    async def check_requires_approval(
        self,
        action: ApprovalAction,
        resource_id: UUID,
        context: dict[str, Any] | None = None,
    ) -> tuple[bool, ApprovalPolicy | None]:
        """Check if an action requires approval."""
        for policy in self._policies.values():
            if not policy.enabled:
                continue
            if action not in policy.actions:
                continue

            # Check conditions
            if context and policy.conditions:
                if policy.auto_approve_confidence:
                    confidence = context.get("confidence", 0)
                    if confidence >= policy.auto_approve_confidence:
                        self._logger.info(
                            "Auto-approving due to high confidence",
                            action=action,
                            confidence=confidence,
                        )
                        return False, None

            return True, policy

        return False, None

    async def request_approval(
        self,
        action: ApprovalAction,
        resource_id: UUID,
        requested_by: UUID,
        details: dict[str, Any] | None = None,
    ) -> ApprovalRequest:
        """Create an approval request."""
        from datetime import timedelta

        requires, policy = await self.check_requires_approval(
            action, resource_id, details
        )

        if not requires:
            # Return auto-approved request
            return ApprovalRequest(
                tenant_id=self.tenant_id,
                action=action,
                resource_id=resource_id,
                requested_by=requested_by,
                status=ApprovalStatus.APPROVED,
                details=details or {},
                reviewed_by=requested_by,
                reviewed_at=datetime.now(timezone.utc),
                review_comment="Auto-approved",
            )

        expires_at = None
        if policy and policy.timeout_hours:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=policy.timeout_hours)

        request = ApprovalRequest(
            tenant_id=self.tenant_id,
            action=action,
            resource_id=resource_id,
            requested_by=requested_by,
            details=details or {},
            expires_at=expires_at,
        )

        self._requests[request.id] = request

        self._logger.info(
            "Approval requested",
            request_id=str(request.id),
            action=action,
            resource_id=str(resource_id),
        )

        return request

    async def approve(
        self,
        request_id: UUID,
        approved_by: UUID,
        comment: str | None = None,
    ) -> ApprovalRequest:
        """Approve a request."""
        request = self._requests.get(request_id)
        if not request:
            raise ValueError(f"Request {request_id} not found")

        if request.status != ApprovalStatus.PENDING:
            raise ValueError(f"Request is not pending: {request.status}")

        request.status = ApprovalStatus.APPROVED
        request.reviewed_by = approved_by
        request.reviewed_at = datetime.now(timezone.utc)
        request.review_comment = comment

        self._logger.info(
            "Request approved",
            request_id=str(request_id),
            approved_by=str(approved_by),
        )

        return request

    async def reject(
        self,
        request_id: UUID,
        rejected_by: UUID,
        comment: str | None = None,
    ) -> ApprovalRequest:
        """Reject a request."""
        request = self._requests.get(request_id)
        if not request:
            raise ValueError(f"Request {request_id} not found")

        if request.status != ApprovalStatus.PENDING:
            raise ValueError(f"Request is not pending: {request.status}")

        request.status = ApprovalStatus.REJECTED
        request.reviewed_by = rejected_by
        request.reviewed_at = datetime.now(timezone.utc)
        request.review_comment = comment

        self._logger.info(
            "Request rejected",
            request_id=str(request_id),
            rejected_by=str(rejected_by),
        )

        return request

    async def get_pending_requests(
        self,
        user_id: UUID | None = None,
        resource_id: UUID | None = None,
    ) -> list[ApprovalRequest]:
        """Get pending approval requests."""
        requests = []
        for request in self._requests.values():
            if request.status != ApprovalStatus.PENDING:
                continue
            if resource_id and request.resource_id != resource_id:
                continue
            requests.append(request)

        return requests

    def add_policy(self, policy: ApprovalPolicy) -> None:
        """Add an approval policy."""
        self._policies[policy.id] = policy

    def remove_policy(self, policy_id: UUID) -> None:
        """Remove an approval policy."""
        self._policies.pop(policy_id, None)


class AccessControl:
    """Role-based access control for agents."""

    def __init__(self, tenant_id: UUID):
        self.tenant_id = tenant_id
        self._user_roles: dict[UUID, list[str]] = {}
        self._custom_roles: dict[str, Role] = {}
        self._logger = logger.bind(
            component="AccessControl",
            tenant_id=str(tenant_id),
        )

    def get_role(self, role_id: str) -> Role | None:
        """Get a role by ID."""
        if role_id in PREDEFINED_ROLES:
            return PREDEFINED_ROLES[role_id]
        return self._custom_roles.get(role_id)

    def assign_role(self, user_id: UUID, role_id: str) -> None:
        """Assign a role to a user."""
        if user_id not in self._user_roles:
            self._user_roles[user_id] = []
        if role_id not in self._user_roles[user_id]:
            self._user_roles[user_id].append(role_id)
            self._logger.info(
                "Role assigned",
                user_id=str(user_id),
                role_id=role_id,
            )

    def remove_role(self, user_id: UUID, role_id: str) -> None:
        """Remove a role from a user."""
        if user_id in self._user_roles:
            self._user_roles[user_id] = [
                r for r in self._user_roles[user_id] if r != role_id
            ]
            self._logger.info(
                "Role removed",
                user_id=str(user_id),
                role_id=role_id,
            )

    def get_user_roles(self, user_id: UUID) -> list[Role]:
        """Get all roles for a user."""
        role_ids = self._user_roles.get(user_id, [])
        roles = []
        for role_id in role_ids:
            role = self.get_role(role_id)
            if role:
                roles.append(role)
        return roles

    def get_user_permissions(self, user_id: UUID) -> set[Permission]:
        """Get all permissions for a user."""
        permissions: set[Permission] = set()
        for role in self.get_user_roles(user_id):
            permissions.update(role.permissions)
        return permissions

    def has_permission(self, user_id: UUID, permission: Permission) -> bool:
        """Check if user has a specific permission."""
        return permission in self.get_user_permissions(user_id)

    def check_access(
        self,
        user_id: UUID,
        action: str,
        resource_type: str = "agent",
        resource_id: UUID | None = None,
    ) -> bool:
        """Check if user can perform action on resource."""
        permission_map = {
            "view": Permission.AGENT_VIEW,
            "create": Permission.AGENT_CREATE,
            "edit": Permission.AGENT_EDIT,
            "delete": Permission.AGENT_DELETE,
            "activate": Permission.AGENT_ACTIVATE,
            "execute": Permission.AGENT_EXECUTE,
            "approve": Permission.AGENT_APPROVE,
        }

        permission = permission_map.get(action)
        if not permission:
            return False

        return self.has_permission(user_id, permission)

    def create_custom_role(self, role: Role) -> Role:
        """Create a custom role."""
        if role.id in PREDEFINED_ROLES:
            raise ValueError(f"Cannot override system role: {role.id}")
        role.is_system = False
        self._custom_roles[role.id] = role
        return role
