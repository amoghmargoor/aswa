# Task 9.6.3: Agent Permissions

## Objective

Implement a comprehensive permissions system for agents, controlling what actions agents can perform and what resources they can access.

## Prerequisites

- Task 9.6.1-9.6.2 completed (Approval Service and UI)
- Role-based access control foundation

## Implementation

### Step 1: Permission Models

```python
# services/agent-service/src/aswa_agents/models/permissions.py
"""Permission models for agents."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import Column, String, DateTime, JSON, Boolean, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from aswa_agents.db.base import Base


class Permission(str, Enum):
    """Agent permission types."""

    # Action permissions
    ACTION_SEND_EMAIL = "action:send_email"
    ACTION_SEND_SLACK = "action:send_slack"
    ACTION_CREATE_TICKET = "action:create_ticket"
    ACTION_HTTP_REQUEST = "action:http_request"
    ACTION_QUERY_KNOWLEDGE = "action:query_knowledge"
    ACTION_SUMMARIZE = "action:summarize"
    ACTION_EXTRACT = "action:extract"
    ACTION_TRANSFORM = "action:transform"

    # Resource permissions
    RESOURCE_READ_EMAILS = "resource:read_emails"
    RESOURCE_READ_DOCUMENTS = "resource:read_documents"
    RESOURCE_READ_SLACK = "resource:read_slack"
    RESOURCE_READ_CALENDAR = "resource:read_calendar"
    RESOURCE_WRITE_EXTERNAL = "resource:write_external"

    # Integration permissions
    INTEGRATION_SLACK = "integration:slack"
    INTEGRATION_EMAIL = "integration:email"
    INTEGRATION_JIRA = "integration:jira"
    INTEGRATION_LINEAR = "integration:linear"
    INTEGRATION_GITHUB = "integration:github"
    INTEGRATION_CUSTOM_API = "integration:custom_api"

    # Data access permissions
    DATA_PII = "data:pii"
    DATA_SENSITIVE = "data:sensitive"
    DATA_FINANCIAL = "data:financial"
    DATA_INTERNAL = "data:internal"

    # Operational permissions
    OPS_EXECUTE_AUTONOMOUSLY = "ops:execute_autonomously"
    OPS_SCHEDULE = "ops:schedule"
    OPS_BATCH_OPERATIONS = "ops:batch_operations"


class PermissionScope(str, Enum):
    """Permission scope levels."""

    GLOBAL = "global"  # All resources of type
    TENANT = "tenant"  # Within tenant
    USER = "user"  # User's own resources
    AGENT = "agent"  # Agent's own resources
    RESTRICTED = "restricted"  # Specific resources only


class AgentPermissionModel(Base):
    """SQLAlchemy model for agent permissions."""

    __tablename__ = "agent_permissions"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id = Column(PGUUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    tenant_id = Column(String(100), nullable=False)

    # Permission details
    permission = Column(String(100), nullable=False)
    scope = Column(String(50), default=PermissionScope.TENANT.value)
    scope_value = Column(String(200), nullable=True)  # Specific resource ID if restricted

    # Constraints
    conditions = Column(JSON, default=dict)  # Additional conditions
    rate_limit = Column(JSON, nullable=True)  # Rate limiting config
    allowed_values = Column(JSON, nullable=True)  # Allowed parameter values

    # Status
    granted = Column(Boolean, default=True)
    granted_by = Column(String(100), nullable=True)
    granted_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_agent_permissions_agent_id", "agent_id"),
        Index("idx_agent_permissions_tenant_id", "tenant_id"),
        Index("idx_agent_permissions_permission", "permission"),
        UniqueConstraint("agent_id", "permission", "scope", "scope_value", name="uq_agent_permission"),
    )


class PermissionPolicyModel(Base):
    """SQLAlchemy model for permission policies."""

    __tablename__ = "permission_policies"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(String(100), nullable=False)

    # Policy details
    name = Column(String(200), nullable=False)
    description = Column(String(1000), nullable=True)

    # Permissions included
    permissions = Column(JSON, default=list)  # List of permission strings
    conditions = Column(JSON, default=dict)  # Global conditions

    # Applicability
    is_default = Column(Boolean, default=False)
    agent_pattern = Column(String(200), nullable=True)  # Regex for auto-apply

    # Status
    enabled = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_permission_policies_tenant_id", "tenant_id"),
    )


# Pydantic models
class PermissionGrant(BaseModel):
    """Grant a permission to an agent."""

    permission: str
    scope: PermissionScope = PermissionScope.TENANT
    scope_value: str | None = None
    conditions: dict[str, Any] = Field(default_factory=dict)
    rate_limit: dict[str, Any] | None = None
    allowed_values: list[Any] | None = None
    expires_at: datetime | None = None


class PermissionCheck(BaseModel):
    """Check permission request."""

    permission: str
    resource_id: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class PermissionCheckResult(BaseModel):
    """Permission check result."""

    allowed: bool
    permission: str
    reason: str | None = None
    rate_limited: bool = False
    conditions_met: bool = True


class PermissionPolicy(BaseModel):
    """Permission policy definition."""

    name: str
    description: str | None = None
    permissions: list[str]
    conditions: dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False
    agent_pattern: str | None = None


class AgentPermissions(BaseModel):
    """Complete permissions for an agent."""

    agent_id: UUID
    permissions: list[dict[str, Any]]
    policies: list[str]
    effective_permissions: list[str]
```

### Step 2: Permission Repository

```python
# services/agent-service/src/aswa_agents/repositories/permission_repository.py
"""Repository for permission management."""

from datetime import datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from aswa_agents.db.session import get_session
from aswa_agents.models.permissions import (
    AgentPermissionModel,
    PermissionPolicyModel,
    Permission,
    PermissionScope,
    PermissionGrant,
)

logger = structlog.get_logger()


class PermissionRepository:
    """Repository for managing agent permissions."""

    def __init__(self, session: AsyncSession | None = None):
        self._session = session
        self._logger = logger.bind(component="PermissionRepository")

    async def _get_session(self) -> AsyncSession:
        if self._session:
            return self._session
        return await get_session()

    async def grant_permission(
        self,
        agent_id: UUID,
        tenant_id: str,
        grant: PermissionGrant,
        granted_by: str,
    ) -> AgentPermissionModel:
        """Grant a permission to an agent."""
        session = await self._get_session()

        # Check if permission already exists
        existing = await self.get_permission(
            agent_id, tenant_id, grant.permission, grant.scope, grant.scope_value
        )

        if existing:
            # Update existing
            existing.conditions = grant.conditions
            existing.rate_limit = grant.rate_limit
            existing.allowed_values = grant.allowed_values
            existing.expires_at = grant.expires_at
            existing.granted = True
            existing.granted_by = granted_by
            existing.granted_at = datetime.utcnow()
            await session.commit()
            return existing

        # Create new
        permission = AgentPermissionModel(
            agent_id=agent_id,
            tenant_id=tenant_id,
            permission=grant.permission,
            scope=grant.scope.value,
            scope_value=grant.scope_value,
            conditions=grant.conditions,
            rate_limit=grant.rate_limit,
            allowed_values=grant.allowed_values,
            expires_at=grant.expires_at,
            granted_by=granted_by,
        )

        session.add(permission)
        await session.commit()
        await session.refresh(permission)

        self._logger.info(
            "Granted permission",
            agent_id=str(agent_id),
            permission=grant.permission,
            granted_by=granted_by,
        )

        return permission

    async def revoke_permission(
        self,
        agent_id: UUID,
        tenant_id: str,
        permission: str,
        scope: PermissionScope = PermissionScope.TENANT,
        scope_value: str | None = None,
    ) -> bool:
        """Revoke a permission from an agent."""
        session = await self._get_session()

        conditions = [
            AgentPermissionModel.agent_id == agent_id,
            AgentPermissionModel.tenant_id == tenant_id,
            AgentPermissionModel.permission == permission,
            AgentPermissionModel.scope == scope.value,
        ]

        if scope_value:
            conditions.append(AgentPermissionModel.scope_value == scope_value)

        result = await session.execute(
            delete(AgentPermissionModel).where(and_(*conditions))
        )

        await session.commit()

        return result.rowcount > 0

    async def get_permission(
        self,
        agent_id: UUID,
        tenant_id: str,
        permission: str,
        scope: PermissionScope = PermissionScope.TENANT,
        scope_value: str | None = None,
    ) -> AgentPermissionModel | None:
        """Get a specific permission."""
        session = await self._get_session()

        conditions = [
            AgentPermissionModel.agent_id == agent_id,
            AgentPermissionModel.tenant_id == tenant_id,
            AgentPermissionModel.permission == permission,
            AgentPermissionModel.scope == scope.value,
        ]

        if scope_value:
            conditions.append(AgentPermissionModel.scope_value == scope_value)

        result = await session.execute(
            select(AgentPermissionModel).where(and_(*conditions))
        )

        return result.scalar_one_or_none()

    async def list_agent_permissions(
        self,
        agent_id: UUID,
        tenant_id: str,
    ) -> list[AgentPermissionModel]:
        """List all permissions for an agent."""
        session = await self._get_session()

        result = await session.execute(
            select(AgentPermissionModel).where(
                and_(
                    AgentPermissionModel.agent_id == agent_id,
                    AgentPermissionModel.tenant_id == tenant_id,
                    AgentPermissionModel.granted == True,
                )
            )
        )

        return result.scalars().all()

    async def check_permission(
        self,
        agent_id: UUID,
        tenant_id: str,
        permission: str,
        resource_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> tuple[bool, str | None]:
        """
        Check if agent has permission.

        Returns (allowed, reason).
        """
        permissions = await self.list_agent_permissions(agent_id, tenant_id)

        for perm in permissions:
            if perm.permission != permission:
                continue

            # Check expiration
            if perm.expires_at and perm.expires_at < datetime.utcnow():
                continue

            # Check scope
            if perm.scope == PermissionScope.RESTRICTED.value:
                if resource_id and perm.scope_value != resource_id:
                    continue

            # Check conditions
            if perm.conditions and context:
                if not self._evaluate_conditions(perm.conditions, context):
                    return False, "Conditions not met"

            # Check rate limit
            if perm.rate_limit:
                if await self._check_rate_limit(agent_id, permission, perm.rate_limit):
                    return False, "Rate limit exceeded"

            # Check allowed values
            if perm.allowed_values and context:
                value = context.get("value")
                if value and value not in perm.allowed_values:
                    return False, f"Value not in allowed list"

            return True, None

        # Check policies
        policies = await self.list_agent_policies(agent_id, tenant_id)
        for policy in policies:
            if permission in policy.permissions:
                if policy.conditions and context:
                    if not self._evaluate_conditions(policy.conditions, context):
                        continue
                return True, None

        return False, "Permission not granted"

    def _evaluate_conditions(
        self,
        conditions: dict[str, Any],
        context: dict[str, Any],
    ) -> bool:
        """Evaluate permission conditions."""
        for key, expected in conditions.items():
            actual = context.get(key)

            if isinstance(expected, dict):
                op = expected.get("op", "eq")
                value = expected.get("value")

                if op == "eq" and actual != value:
                    return False
                elif op == "ne" and actual == value:
                    return False
                elif op == "in" and actual not in value:
                    return False
                elif op == "not_in" and actual in value:
                    return False
                elif op == "gt" and not (actual and actual > value):
                    return False
                elif op == "lt" and not (actual and actual < value):
                    return False
            else:
                if actual != expected:
                    return False

        return True

    async def _check_rate_limit(
        self,
        agent_id: UUID,
        permission: str,
        rate_limit: dict[str, Any],
    ) -> bool:
        """Check if rate limit is exceeded."""
        # Implementation would use Redis or similar for rate limiting
        # Returns True if rate limited
        return False

    # Policy methods

    async def create_policy(
        self,
        tenant_id: str,
        policy: dict[str, Any],
    ) -> PermissionPolicyModel:
        """Create a permission policy."""
        session = await self._get_session()

        db_policy = PermissionPolicyModel(
            tenant_id=tenant_id,
            name=policy["name"],
            description=policy.get("description"),
            permissions=policy.get("permissions", []),
            conditions=policy.get("conditions", {}),
            is_default=policy.get("is_default", False),
            agent_pattern=policy.get("agent_pattern"),
            enabled=policy.get("enabled", True),
        )

        session.add(db_policy)
        await session.commit()
        await session.refresh(db_policy)

        return db_policy

    async def list_policies(
        self,
        tenant_id: str,
        enabled_only: bool = True,
    ) -> list[PermissionPolicyModel]:
        """List all policies."""
        session = await self._get_session()

        conditions = [PermissionPolicyModel.tenant_id == tenant_id]
        if enabled_only:
            conditions.append(PermissionPolicyModel.enabled == True)

        result = await session.execute(
            select(PermissionPolicyModel).where(and_(*conditions))
        )

        return result.scalars().all()

    async def list_agent_policies(
        self,
        agent_id: UUID,
        tenant_id: str,
    ) -> list[PermissionPolicyModel]:
        """Get policies applicable to an agent."""
        import re

        # Get agent name for pattern matching
        from aswa_agents.repositories.agent_repository import AgentRepository
        agent_repo = AgentRepository()
        agent = await agent_repo.get_by_id(str(agent_id))
        agent_name = agent.name if agent else ""

        all_policies = await self.list_policies(tenant_id)
        matching = []

        for policy in all_policies:
            # Check if default
            if policy.is_default:
                matching.append(policy)
                continue

            # Check pattern
            if policy.agent_pattern:
                try:
                    if re.match(policy.agent_pattern, agent_name):
                        matching.append(policy)
                except re.error:
                    continue

        return matching

    async def apply_default_permissions(
        self,
        agent_id: UUID,
        tenant_id: str,
        granted_by: str,
    ) -> list[AgentPermissionModel]:
        """Apply default permissions to a new agent."""
        default_policies = await self.list_policies(tenant_id)
        default_policies = [p for p in default_policies if p.is_default]

        granted = []
        for policy in default_policies:
            for permission in policy.permissions:
                grant = PermissionGrant(
                    permission=permission,
                    conditions=policy.conditions,
                )
                perm = await self.grant_permission(
                    agent_id, tenant_id, grant, granted_by
                )
                granted.append(perm)

        return granted
```

### Step 3: Permission Service

```python
# services/agent-service/src/aswa_agents/services/permission_service.py
"""Permission service for agent authorization."""

from typing import Any
from uuid import UUID

import structlog

from aswa_agents.models.permissions import (
    Permission,
    PermissionScope,
    PermissionGrant,
    PermissionCheck,
    PermissionCheckResult,
    PermissionPolicy,
    AgentPermissions,
)
from aswa_agents.repositories.permission_repository import PermissionRepository

logger = structlog.get_logger()


class PermissionService:
    """
    Service for managing agent permissions.

    Provides authorization checks and permission management.
    """

    # Default permissions for different agent types
    DEFAULT_PERMISSIONS = {
        "basic": [
            Permission.ACTION_SUMMARIZE,
            Permission.ACTION_EXTRACT,
            Permission.ACTION_TRANSFORM,
            Permission.ACTION_QUERY_KNOWLEDGE,
            Permission.RESOURCE_READ_DOCUMENTS,
        ],
        "communication": [
            Permission.ACTION_SEND_EMAIL,
            Permission.ACTION_SEND_SLACK,
            Permission.INTEGRATION_EMAIL,
            Permission.INTEGRATION_SLACK,
        ],
        "ticketing": [
            Permission.ACTION_CREATE_TICKET,
            Permission.INTEGRATION_JIRA,
            Permission.INTEGRATION_LINEAR,
        ],
        "full": list(Permission),
    }

    def __init__(self):
        self._repo = PermissionRepository()
        self._logger = logger.bind(component="PermissionService")

    async def check_permission(
        self,
        agent_id: UUID,
        tenant_id: str,
        check: PermissionCheck,
    ) -> PermissionCheckResult:
        """
        Check if agent has permission.

        Args:
            agent_id: Agent to check
            tenant_id: Tenant context
            check: Permission check request

        Returns:
            PermissionCheckResult with allowed status
        """
        allowed, reason = await self._repo.check_permission(
            agent_id=agent_id,
            tenant_id=tenant_id,
            permission=check.permission,
            resource_id=check.resource_id,
            context=check.context,
        )

        self._logger.debug(
            "Permission check",
            agent_id=str(agent_id),
            permission=check.permission,
            allowed=allowed,
            reason=reason,
        )

        return PermissionCheckResult(
            allowed=allowed,
            permission=check.permission,
            reason=reason,
        )

    async def check_action_permission(
        self,
        agent_id: UUID,
        tenant_id: str,
        action_type: str,
        context: dict[str, Any] | None = None,
    ) -> PermissionCheckResult:
        """Check permission for an action type."""
        # Map action type to permission
        permission_map = {
            "summarize": Permission.ACTION_SUMMARIZE,
            "extract": Permission.ACTION_EXTRACT,
            "transform": Permission.ACTION_TRANSFORM,
            "query_knowledge": Permission.ACTION_QUERY_KNOWLEDGE,
            "send_email": Permission.ACTION_SEND_EMAIL,
            "send_slack": Permission.ACTION_SEND_SLACK,
            "create_ticket": Permission.ACTION_CREATE_TICKET,
            "http_request": Permission.ACTION_HTTP_REQUEST,
        }

        permission = permission_map.get(action_type)
        if not permission:
            return PermissionCheckResult(
                allowed=True,
                permission=f"action:{action_type}",
                reason="No permission required",
            )

        return await self.check_permission(
            agent_id,
            tenant_id,
            PermissionCheck(permission=permission.value, context=context or {}),
        )

    async def grant_permissions(
        self,
        agent_id: UUID,
        tenant_id: str,
        permissions: list[PermissionGrant],
        granted_by: str,
    ) -> list[dict[str, Any]]:
        """Grant multiple permissions to an agent."""
        results = []

        for grant in permissions:
            perm = await self._repo.grant_permission(
                agent_id, tenant_id, grant, granted_by
            )
            results.append({
                "permission": grant.permission,
                "scope": grant.scope.value,
                "granted": True,
            })

        self._logger.info(
            "Granted permissions",
            agent_id=str(agent_id),
            count=len(permissions),
            granted_by=granted_by,
        )

        return results

    async def revoke_permissions(
        self,
        agent_id: UUID,
        tenant_id: str,
        permissions: list[str],
    ) -> list[dict[str, Any]]:
        """Revoke permissions from an agent."""
        results = []

        for permission in permissions:
            success = await self._repo.revoke_permission(
                agent_id, tenant_id, permission
            )
            results.append({
                "permission": permission,
                "revoked": success,
            })

        return results

    async def get_agent_permissions(
        self,
        agent_id: UUID,
        tenant_id: str,
    ) -> AgentPermissions:
        """Get all permissions for an agent."""
        permissions = await self._repo.list_agent_permissions(agent_id, tenant_id)
        policies = await self._repo.list_agent_policies(agent_id, tenant_id)

        # Calculate effective permissions
        effective = set()
        for perm in permissions:
            if perm.granted:
                effective.add(perm.permission)

        for policy in policies:
            for perm in policy.permissions:
                effective.add(perm)

        return AgentPermissions(
            agent_id=agent_id,
            permissions=[
                {
                    "permission": p.permission,
                    "scope": p.scope,
                    "scope_value": p.scope_value,
                    "conditions": p.conditions,
                    "expires_at": p.expires_at.isoformat() if p.expires_at else None,
                }
                for p in permissions
            ],
            policies=[p.name for p in policies],
            effective_permissions=list(effective),
        )

    async def apply_permission_template(
        self,
        agent_id: UUID,
        tenant_id: str,
        template: str,
        granted_by: str,
    ) -> list[dict[str, Any]]:
        """Apply a permission template to an agent."""
        template_permissions = self.DEFAULT_PERMISSIONS.get(template, [])

        grants = [
            PermissionGrant(permission=p.value if isinstance(p, Permission) else p)
            for p in template_permissions
        ]

        return await self.grant_permissions(agent_id, tenant_id, grants, granted_by)

    async def create_policy(
        self,
        tenant_id: str,
        policy: PermissionPolicy,
    ) -> dict[str, Any]:
        """Create a permission policy."""
        db_policy = await self._repo.create_policy(
            tenant_id,
            policy.model_dump(),
        )

        return {
            "id": str(db_policy.id),
            "name": db_policy.name,
            "permissions": db_policy.permissions,
            "created": True,
        }

    async def list_policies(
        self,
        tenant_id: str,
    ) -> list[dict[str, Any]]:
        """List all policies."""
        policies = await self._repo.list_policies(tenant_id)

        return [
            {
                "id": str(p.id),
                "name": p.name,
                "description": p.description,
                "permissions": p.permissions,
                "is_default": p.is_default,
                "agent_pattern": p.agent_pattern,
                "enabled": p.enabled,
            }
            for p in policies
        ]

    async def validate_agent_actions(
        self,
        agent_id: UUID,
        tenant_id: str,
        action_types: list[str],
    ) -> list[dict[str, Any]]:
        """Validate that agent has permissions for all actions."""
        results = []

        for action_type in action_types:
            check = await self.check_action_permission(
                agent_id, tenant_id, action_type
            )
            results.append({
                "action_type": action_type,
                "allowed": check.allowed,
                "reason": check.reason,
            })

        return results
```

### Step 4: Permission API Endpoints

```python
# services/agent-service/src/aswa_agents/api/permissions.py
"""API endpoints for permissions."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from aswa_agents.models.permissions import (
    PermissionGrant,
    PermissionCheck,
    PermissionCheckResult,
    PermissionPolicy,
    PermissionScope,
)
from aswa_agents.services.permission_service import PermissionService

router = APIRouter(prefix="/permissions", tags=["permissions"])


class GrantPermissionsRequest(BaseModel):
    """Request to grant permissions."""

    permissions: list[PermissionGrant]


class RevokePermissionsRequest(BaseModel):
    """Request to revoke permissions."""

    permissions: list[str]


class ApplyTemplateRequest(BaseModel):
    """Request to apply permission template."""

    template: str  # basic, communication, ticketing, full


class ValidateActionsRequest(BaseModel):
    """Request to validate agent actions."""

    action_types: list[str]


@router.get("/agents/{agent_id}")
async def get_agent_permissions(agent_id: UUID) -> dict[str, Any]:
    """Get all permissions for an agent."""
    tenant_id = "default-tenant"  # From auth

    service = PermissionService()
    permissions = await service.get_agent_permissions(agent_id, tenant_id)

    return permissions.model_dump()


@router.post("/agents/{agent_id}/grant")
async def grant_permissions(
    agent_id: UUID,
    request: GrantPermissionsRequest,
) -> dict[str, Any]:
    """Grant permissions to an agent."""
    tenant_id = "default-tenant"
    user_id = "current-user"

    service = PermissionService()
    results = await service.grant_permissions(
        agent_id, tenant_id, request.permissions, user_id
    )

    return {"granted": results}


@router.post("/agents/{agent_id}/revoke")
async def revoke_permissions(
    agent_id: UUID,
    request: RevokePermissionsRequest,
) -> dict[str, Any]:
    """Revoke permissions from an agent."""
    tenant_id = "default-tenant"

    service = PermissionService()
    results = await service.revoke_permissions(
        agent_id, tenant_id, request.permissions
    )

    return {"revoked": results}


@router.post("/agents/{agent_id}/check")
async def check_permission(
    agent_id: UUID,
    check: PermissionCheck,
) -> PermissionCheckResult:
    """Check if agent has a permission."""
    tenant_id = "default-tenant"

    service = PermissionService()
    return await service.check_permission(agent_id, tenant_id, check)


@router.post("/agents/{agent_id}/apply-template")
async def apply_template(
    agent_id: UUID,
    request: ApplyTemplateRequest,
) -> dict[str, Any]:
    """Apply a permission template to an agent."""
    tenant_id = "default-tenant"
    user_id = "current-user"

    service = PermissionService()
    results = await service.apply_permission_template(
        agent_id, tenant_id, request.template, user_id
    )

    return {"applied": results, "template": request.template}


@router.post("/agents/{agent_id}/validate")
async def validate_actions(
    agent_id: UUID,
    request: ValidateActionsRequest,
) -> dict[str, Any]:
    """Validate agent has permissions for actions."""
    tenant_id = "default-tenant"

    service = PermissionService()
    results = await service.validate_agent_actions(
        agent_id, tenant_id, request.action_types
    )

    all_allowed = all(r["allowed"] for r in results)

    return {
        "valid": all_allowed,
        "results": results,
    }


# Policy endpoints

@router.get("/policies")
async def list_policies() -> dict[str, Any]:
    """List all permission policies."""
    tenant_id = "default-tenant"

    service = PermissionService()
    policies = await service.list_policies(tenant_id)

    return {"policies": policies}


@router.post("/policies")
async def create_policy(policy: PermissionPolicy) -> dict[str, Any]:
    """Create a permission policy."""
    tenant_id = "default-tenant"

    service = PermissionService()
    result = await service.create_policy(tenant_id, policy)

    return result


@router.get("/templates")
async def list_templates() -> dict[str, Any]:
    """List available permission templates."""
    return {
        "templates": {
            name: [p.value if hasattr(p, "value") else p for p in perms]
            for name, perms in PermissionService.DEFAULT_PERMISSIONS.items()
        }
    }
```

## Test Cases

```python
# services/agent-service/tests/unit/test_permissions.py
"""Tests for agent permissions."""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, patch

from aswa_agents.models.permissions import (
    Permission,
    PermissionScope,
    PermissionGrant,
    PermissionCheck,
)
from aswa_agents.services.permission_service import PermissionService
from aswa_agents.repositories.permission_repository import PermissionRepository


class TestPermissionRepository:
    """Test PermissionRepository."""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_grant_permission(self, mock_session):
        """Test granting a permission."""
        repo = PermissionRepository(session=mock_session)

        grant = PermissionGrant(
            permission=Permission.ACTION_SEND_EMAIL.value,
            scope=PermissionScope.TENANT,
        )

        mock_session.execute.return_value = AsyncMock(
            scalar_one_or_none=lambda: None
        )

        result = await repo.grant_permission(
            agent_id=uuid4(),
            tenant_id="test",
            grant=grant,
            granted_by="admin",
        )

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_check_permission_granted(self, mock_session):
        """Test checking a granted permission."""
        repo = PermissionRepository(session=mock_session)

        mock_perm = AsyncMock()
        mock_perm.permission = Permission.ACTION_SEND_EMAIL.value
        mock_perm.scope = PermissionScope.TENANT.value
        mock_perm.scope_value = None
        mock_perm.expires_at = None
        mock_perm.conditions = {}
        mock_perm.rate_limit = None
        mock_perm.allowed_values = None
        mock_perm.granted = True

        mock_session.execute.return_value = AsyncMock(
            scalars=lambda: AsyncMock(all=lambda: [mock_perm])
        )

        # Mock list_agent_policies to return empty
        with patch.object(repo, "list_agent_policies", return_value=[]):
            allowed, reason = await repo.check_permission(
                agent_id=uuid4(),
                tenant_id="test",
                permission=Permission.ACTION_SEND_EMAIL.value,
            )

        assert allowed is True
        assert reason is None

    @pytest.mark.asyncio
    async def test_check_permission_not_granted(self, mock_session):
        """Test checking a non-granted permission."""
        repo = PermissionRepository(session=mock_session)

        mock_session.execute.return_value = AsyncMock(
            scalars=lambda: AsyncMock(all=lambda: [])
        )

        with patch.object(repo, "list_agent_policies", return_value=[]):
            allowed, reason = await repo.check_permission(
                agent_id=uuid4(),
                tenant_id="test",
                permission=Permission.ACTION_SEND_EMAIL.value,
            )

        assert allowed is False
        assert reason == "Permission not granted"

    @pytest.mark.asyncio
    async def test_check_permission_expired(self, mock_session):
        """Test checking an expired permission."""
        repo = PermissionRepository(session=mock_session)

        mock_perm = AsyncMock()
        mock_perm.permission = Permission.ACTION_SEND_EMAIL.value
        mock_perm.expires_at = datetime.utcnow() - timedelta(hours=1)  # Expired
        mock_perm.granted = True

        mock_session.execute.return_value = AsyncMock(
            scalars=lambda: AsyncMock(all=lambda: [mock_perm])
        )

        with patch.object(repo, "list_agent_policies", return_value=[]):
            allowed, reason = await repo.check_permission(
                agent_id=uuid4(),
                tenant_id="test",
                permission=Permission.ACTION_SEND_EMAIL.value,
            )

        assert allowed is False

    def test_evaluate_conditions(self, mock_session):
        """Test condition evaluation."""
        repo = PermissionRepository(session=mock_session)

        conditions = {
            "priority": "high",
            "amount": {"op": "lt", "value": 1000},
        }

        context = {"priority": "high", "amount": 500}
        assert repo._evaluate_conditions(conditions, context) is True

        context = {"priority": "low", "amount": 500}
        assert repo._evaluate_conditions(conditions, context) is False

        context = {"priority": "high", "amount": 1500}
        assert repo._evaluate_conditions(conditions, context) is False


class TestPermissionService:
    """Test PermissionService."""

    @pytest.fixture
    def service(self):
        return PermissionService()

    @pytest.mark.asyncio
    async def test_check_action_permission(self, service):
        """Test checking action permission."""
        with patch.object(service._repo, "check_permission") as mock:
            mock.return_value = (True, None)

            result = await service.check_action_permission(
                agent_id=uuid4(),
                tenant_id="test",
                action_type="send_email",
            )

            assert result.allowed is True
            assert result.permission == Permission.ACTION_SEND_EMAIL.value

    @pytest.mark.asyncio
    async def test_check_unknown_action(self, service):
        """Test checking unknown action type."""
        result = await service.check_action_permission(
            agent_id=uuid4(),
            tenant_id="test",
            action_type="unknown_action",
        )

        assert result.allowed is True
        assert result.reason == "No permission required"

    @pytest.mark.asyncio
    async def test_apply_permission_template(self, service):
        """Test applying permission template."""
        with patch.object(service, "grant_permissions") as mock:
            mock.return_value = [{"permission": "test", "granted": True}]

            result = await service.apply_permission_template(
                agent_id=uuid4(),
                tenant_id="test",
                template="basic",
                granted_by="admin",
            )

            mock.assert_called_once()
            # Verify correct permissions are granted
            call_args = mock.call_args
            grants = call_args[0][2]
            assert len(grants) == len(service.DEFAULT_PERMISSIONS["basic"])

    @pytest.mark.asyncio
    async def test_validate_agent_actions(self, service):
        """Test validating agent actions."""
        with patch.object(service, "check_action_permission") as mock:
            mock.side_effect = [
                AsyncMock(allowed=True, reason=None),
                AsyncMock(allowed=False, reason="Not granted"),
            ]

            results = await service.validate_agent_actions(
                agent_id=uuid4(),
                tenant_id="test",
                action_types=["summarize", "send_email"],
            )

            assert len(results) == 2
            assert results[0]["allowed"] is True
            assert results[1]["allowed"] is False


class TestPermissionPolicies:
    """Test permission policies."""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_create_policy(self, mock_session):
        """Test creating a policy."""
        repo = PermissionRepository(session=mock_session)

        policy = {
            "name": "Basic Agent Policy",
            "permissions": [Permission.ACTION_SUMMARIZE.value],
            "is_default": True,
        }

        await repo.create_policy("test", policy)

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_list_agent_policies(self, mock_session):
        """Test listing policies for an agent."""
        repo = PermissionRepository(session=mock_session)

        mock_policy = AsyncMock()
        mock_policy.is_default = True
        mock_policy.agent_pattern = None
        mock_policy.permissions = [Permission.ACTION_SUMMARIZE.value]

        mock_session.execute.return_value = AsyncMock(
            scalars=lambda: AsyncMock(all=lambda: [mock_policy])
        )

        with patch("aswa_agents.repositories.permission_repository.AgentRepository") as mock_repo:
            mock_repo.return_value.get_by_id = AsyncMock(
                return_value=AsyncMock(name="test-agent")
            )

            policies = await repo.list_agent_policies(uuid4(), "test")

        assert len(policies) == 1
```

## Verification Steps

1. **Run unit tests:**
   ```bash
   cd services/agent-service
   pytest tests/unit/test_permissions.py -v
   ```

2. **Test permission granting:**
   ```python
   from aswa_agents.services.permission_service import PermissionService
   from aswa_agents.models.permissions import PermissionGrant, Permission
   from uuid import uuid4

   service = PermissionService()

   # Grant permissions
   results = await service.grant_permissions(
       agent_id=uuid4(),
       tenant_id="test",
       permissions=[
           PermissionGrant(permission=Permission.ACTION_SEND_EMAIL.value),
           PermissionGrant(permission=Permission.ACTION_SEND_SLACK.value),
       ],
       granted_by="admin",
   )
   print(results)
   ```

3. **Test API endpoints:**
   ```bash
   # Get agent permissions
   curl http://localhost:8000/api/v1/permissions/agents/{id}

   # Grant permissions
   curl -X POST http://localhost:8000/api/v1/permissions/agents/{id}/grant \
     -H "Content-Type: application/json" \
     -d '{
       "permissions": [
         {"permission": "action:send_email", "scope": "tenant"}
       ]
     }'

   # Check permission
   curl -X POST http://localhost:8000/api/v1/permissions/agents/{id}/check \
     -H "Content-Type: application/json" \
     -d '{"permission": "action:send_email"}'

   # Apply template
   curl -X POST http://localhost:8000/api/v1/permissions/agents/{id}/apply-template \
     -H "Content-Type: application/json" \
     -d '{"template": "communication"}'
   ```

## Next Task

Proceed to `task-9.6.4-agent-audit-logging.md` for implementing agent audit logging.
