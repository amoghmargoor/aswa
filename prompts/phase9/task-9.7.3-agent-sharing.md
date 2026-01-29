# Task 9.7.3: Agent Sharing

## Objective

Implement agent sharing functionality that allows users to share agents and templates with other users, teams, or make them publicly available within the organization.

## Prerequisites

- Task 9.7.1-9.7.2 completed (Templates)
- Agent definition models
- Multi-tenant architecture

## Implementation

### Step 1: Sharing Models

```python
# services/agent-service/src/aswa_agents/models/sharing.py
"""Agent sharing models."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import Column, String, DateTime, JSON, Boolean, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from aswa_agents.db.base import Base


class ShareType(str, Enum):
    """Types of sharing."""

    USER = "user"  # Share with specific user
    TEAM = "team"  # Share with a team
    ROLE = "role"  # Share with users of specific role
    TENANT = "tenant"  # Share with entire tenant
    PUBLIC = "public"  # Make publicly available


class SharePermission(str, Enum):
    """Permissions for shared resources."""

    VIEW = "view"  # Can view/use
    EDIT = "edit"  # Can modify
    ADMIN = "admin"  # Full control including sharing
    CLONE = "clone"  # Can create copy


class ResourceType(str, Enum):
    """Types of shareable resources."""

    AGENT = "agent"
    TEMPLATE = "template"
    WORKFLOW = "workflow"


class ShareModel(Base):
    """SQLAlchemy model for shares."""

    __tablename__ = "shares"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(String(100), nullable=False)

    # Resource being shared
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(PGUUID(as_uuid=True), nullable=False)
    resource_name = Column(String(200), nullable=True)  # Cached for display

    # Share target
    share_type = Column(String(50), nullable=False)
    target_id = Column(String(200), nullable=True)  # User ID, Team ID, Role name
    target_name = Column(String(200), nullable=True)  # Cached for display

    # Permission
    permission = Column(String(50), default=SharePermission.VIEW.value)

    # Share details
    shared_by = Column(String(100), nullable=False)
    message = Column(String(1000), nullable=True)  # Optional message

    # Status
    active = Column(Boolean, default=True)
    accepted = Column(Boolean, nullable=True)  # For user shares requiring acceptance
    accepted_at = Column(DateTime, nullable=True)

    # Expiration
    expires_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_shares_tenant_id", "tenant_id"),
        Index("idx_shares_resource", "resource_type", "resource_id"),
        Index("idx_shares_target", "share_type", "target_id"),
        Index("idx_shares_shared_by", "shared_by"),
        UniqueConstraint(
            "resource_type", "resource_id", "share_type", "target_id",
            name="uq_share_resource_target"
        ),
    )


class ShareInvitationModel(Base):
    """SQLAlchemy model for share invitations."""

    __tablename__ = "share_invitations"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(String(100), nullable=False)

    # Invitation details
    share_id = Column(PGUUID(as_uuid=True), ForeignKey("shares.id"), nullable=False)
    invitee_email = Column(String(200), nullable=False)
    invitee_id = Column(String(100), nullable=True)  # Set when user exists

    # Token for accepting via link
    token = Column(String(100), unique=True, nullable=False)

    # Status
    status = Column(String(50), default="pending")  # pending, accepted, declined, expired
    responded_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_share_invitations_invitee_email", "invitee_email"),
        Index("idx_share_invitations_token", "token"),
    )


# Pydantic models
class ShareRequest(BaseModel):
    """Request to share a resource."""

    resource_type: ResourceType
    resource_id: UUID
    share_type: ShareType
    target_id: str | None = None  # Required for user/team/role
    permission: SharePermission = SharePermission.VIEW
    message: str | None = None
    expires_at: datetime | None = None


class ShareResponse(BaseModel):
    """Share response."""

    id: UUID
    resource_type: str
    resource_id: UUID
    resource_name: str | None
    share_type: str
    target_id: str | None
    target_name: str | None
    permission: str
    shared_by: str
    message: str | None
    active: bool
    accepted: bool | None
    created_at: datetime
    expires_at: datetime | None


class ShareInvitation(BaseModel):
    """Share invitation for email sharing."""

    email: str
    permission: SharePermission = SharePermission.VIEW
    message: str | None = None


class BulkShareRequest(BaseModel):
    """Request to share with multiple targets."""

    resource_type: ResourceType
    resource_id: UUID
    shares: list[ShareRequest | ShareInvitation]


class SharedWithMe(BaseModel):
    """Resource shared with current user."""

    share_id: UUID
    resource_type: str
    resource_id: UUID
    resource_name: str | None
    permission: str
    shared_by: str
    shared_by_name: str | None
    shared_at: datetime
    message: str | None


class ShareStats(BaseModel):
    """Sharing statistics."""

    total_shared: int
    by_type: dict[str, int]
    by_permission: dict[str, int]
    pending_invitations: int
```

### Step 2: Sharing Repository

```python
# services/agent-service/src/aswa_agents/repositories/sharing_repository.py
"""Repository for sharing management."""

import secrets
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select, and_, or_, delete, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from aswa_agents.db.session import get_session
from aswa_agents.models.sharing import (
    ShareModel,
    ShareInvitationModel,
    ShareType,
    SharePermission,
    ResourceType,
    ShareRequest,
)

logger = structlog.get_logger()


class SharingRepository:
    """Repository for managing shares."""

    def __init__(self, session: AsyncSession | None = None):
        self._session = session
        self._logger = logger.bind(component="SharingRepository")

    async def _get_session(self) -> AsyncSession:
        if self._session:
            return self._session
        return await get_session()

    async def create_share(
        self,
        tenant_id: str,
        request: ShareRequest,
        resource_name: str,
        target_name: str | None,
        shared_by: str,
    ) -> ShareModel:
        """Create a new share."""
        session = await self._get_session()

        # Check if share already exists
        existing = await self.get_share(
            tenant_id,
            request.resource_type.value,
            request.resource_id,
            request.share_type.value,
            request.target_id,
        )

        if existing:
            # Update existing share
            existing.permission = request.permission.value
            existing.message = request.message
            existing.expires_at = request.expires_at
            existing.active = True
            existing.updated_at = datetime.utcnow()
            await session.commit()
            return existing

        share = ShareModel(
            tenant_id=tenant_id,
            resource_type=request.resource_type.value,
            resource_id=request.resource_id,
            resource_name=resource_name,
            share_type=request.share_type.value,
            target_id=request.target_id,
            target_name=target_name,
            permission=request.permission.value,
            shared_by=shared_by,
            message=request.message,
            expires_at=request.expires_at,
            accepted=None if request.share_type == ShareType.USER else True,
        )

        session.add(share)
        await session.commit()
        await session.refresh(share)

        self._logger.info(
            "Share created",
            share_id=str(share.id),
            resource_type=request.resource_type.value,
            share_type=request.share_type.value,
        )

        return share

    async def get_share(
        self,
        tenant_id: str,
        resource_type: str,
        resource_id: UUID,
        share_type: str,
        target_id: str | None,
    ) -> ShareModel | None:
        """Get a specific share."""
        session = await self._get_session()

        conditions = [
            ShareModel.tenant_id == tenant_id,
            ShareModel.resource_type == resource_type,
            ShareModel.resource_id == resource_id,
            ShareModel.share_type == share_type,
        ]

        if target_id:
            conditions.append(ShareModel.target_id == target_id)

        result = await session.execute(
            select(ShareModel).where(and_(*conditions))
        )

        return result.scalar_one_or_none()

    async def get_by_id(
        self,
        share_id: UUID,
        tenant_id: str,
    ) -> ShareModel | None:
        """Get share by ID."""
        session = await self._get_session()

        result = await session.execute(
            select(ShareModel).where(
                and_(
                    ShareModel.id == share_id,
                    ShareModel.tenant_id == tenant_id,
                )
            )
        )

        return result.scalar_one_or_none()

    async def list_resource_shares(
        self,
        tenant_id: str,
        resource_type: str,
        resource_id: UUID,
    ) -> list[ShareModel]:
        """List all shares for a resource."""
        session = await self._get_session()

        result = await session.execute(
            select(ShareModel).where(
                and_(
                    ShareModel.tenant_id == tenant_id,
                    ShareModel.resource_type == resource_type,
                    ShareModel.resource_id == resource_id,
                    ShareModel.active == True,
                )
            ).order_by(ShareModel.created_at.desc())
        )

        return result.scalars().all()

    async def list_shared_with_user(
        self,
        tenant_id: str,
        user_id: str,
        user_teams: list[str] | None = None,
        user_roles: list[str] | None = None,
        resource_type: str | None = None,
    ) -> list[ShareModel]:
        """List all resources shared with a user."""
        session = await self._get_session()

        # Build conditions for different share types
        share_conditions = [
            # Direct user share
            and_(
                ShareModel.share_type == ShareType.USER.value,
                ShareModel.target_id == user_id,
            ),
            # Tenant-wide share
            ShareModel.share_type == ShareType.TENANT.value,
            # Public share
            ShareModel.share_type == ShareType.PUBLIC.value,
        ]

        # Team shares
        if user_teams:
            share_conditions.append(
                and_(
                    ShareModel.share_type == ShareType.TEAM.value,
                    ShareModel.target_id.in_(user_teams),
                )
            )

        # Role shares
        if user_roles:
            share_conditions.append(
                and_(
                    ShareModel.share_type == ShareType.ROLE.value,
                    ShareModel.target_id.in_(user_roles),
                )
            )

        conditions = [
            ShareModel.tenant_id == tenant_id,
            ShareModel.active == True,
            or_(*share_conditions),
            or_(
                ShareModel.expires_at == None,
                ShareModel.expires_at > datetime.utcnow(),
            ),
            or_(
                ShareModel.accepted == True,
                ShareModel.accepted == None,
            ),
        ]

        if resource_type:
            conditions.append(ShareModel.resource_type == resource_type)

        result = await session.execute(
            select(ShareModel)
            .where(and_(*conditions))
            .order_by(ShareModel.created_at.desc())
        )

        return result.scalars().all()

    async def check_access(
        self,
        tenant_id: str,
        resource_type: str,
        resource_id: UUID,
        user_id: str,
        user_teams: list[str] | None = None,
        user_roles: list[str] | None = None,
        required_permission: SharePermission = SharePermission.VIEW,
    ) -> tuple[bool, str | None]:
        """Check if user has access to resource."""
        shares = await self.list_shared_with_user(
            tenant_id=tenant_id,
            user_id=user_id,
            user_teams=user_teams,
            user_roles=user_roles,
            resource_type=resource_type,
        )

        # Filter to matching resource
        resource_shares = [
            s for s in shares if s.resource_id == resource_id
        ]

        if not resource_shares:
            return False, "No share found"

        # Check permission level
        permission_levels = {
            SharePermission.VIEW.value: 1,
            SharePermission.CLONE.value: 2,
            SharePermission.EDIT.value: 3,
            SharePermission.ADMIN.value: 4,
        }

        required_level = permission_levels.get(required_permission.value, 1)

        for share in resource_shares:
            share_level = permission_levels.get(share.permission, 0)
            if share_level >= required_level:
                return True, share.permission

        return False, "Insufficient permissions"

    async def revoke_share(
        self,
        share_id: UUID,
        tenant_id: str,
    ) -> bool:
        """Revoke a share."""
        session = await self._get_session()

        result = await session.execute(
            update(ShareModel)
            .where(
                and_(
                    ShareModel.id == share_id,
                    ShareModel.tenant_id == tenant_id,
                )
            )
            .values(active=False, updated_at=datetime.utcnow())
        )

        await session.commit()

        return result.rowcount > 0

    async def accept_share(
        self,
        share_id: UUID,
        user_id: str,
    ) -> bool:
        """Accept a user share."""
        session = await self._get_session()

        result = await session.execute(
            update(ShareModel)
            .where(
                and_(
                    ShareModel.id == share_id,
                    ShareModel.share_type == ShareType.USER.value,
                    ShareModel.target_id == user_id,
                )
            )
            .values(accepted=True, accepted_at=datetime.utcnow())
        )

        await session.commit()

        return result.rowcount > 0

    async def decline_share(
        self,
        share_id: UUID,
        user_id: str,
    ) -> bool:
        """Decline a user share."""
        session = await self._get_session()

        result = await session.execute(
            update(ShareModel)
            .where(
                and_(
                    ShareModel.id == share_id,
                    ShareModel.share_type == ShareType.USER.value,
                    ShareModel.target_id == user_id,
                )
            )
            .values(accepted=False, active=False)
        )

        await session.commit()

        return result.rowcount > 0

    # Invitation methods

    async def create_invitation(
        self,
        tenant_id: str,
        share_id: UUID,
        email: str,
        expires_hours: int = 168,  # 7 days
    ) -> ShareInvitationModel:
        """Create a share invitation."""
        session = await self._get_session()

        invitation = ShareInvitationModel(
            tenant_id=tenant_id,
            share_id=share_id,
            invitee_email=email,
            token=secrets.token_urlsafe(32),
            expires_at=datetime.utcnow() + timedelta(hours=expires_hours),
        )

        session.add(invitation)
        await session.commit()
        await session.refresh(invitation)

        return invitation

    async def get_invitation_by_token(
        self,
        token: str,
    ) -> ShareInvitationModel | None:
        """Get invitation by token."""
        session = await self._get_session()

        result = await session.execute(
            select(ShareInvitationModel).where(
                and_(
                    ShareInvitationModel.token == token,
                    ShareInvitationModel.expires_at > datetime.utcnow(),
                    ShareInvitationModel.status == "pending",
                )
            )
        )

        return result.scalar_one_or_none()

    async def accept_invitation(
        self,
        invitation_id: UUID,
        user_id: str,
    ) -> bool:
        """Accept an invitation."""
        session = await self._get_session()

        # Update invitation
        await session.execute(
            update(ShareInvitationModel)
            .where(ShareInvitationModel.id == invitation_id)
            .values(
                status="accepted",
                invitee_id=user_id,
                responded_at=datetime.utcnow(),
            )
        )

        # Get the associated share and update target
        result = await session.execute(
            select(ShareInvitationModel).where(
                ShareInvitationModel.id == invitation_id
            )
        )
        invitation = result.scalar_one_or_none()

        if invitation:
            await session.execute(
                update(ShareModel)
                .where(ShareModel.id == invitation.share_id)
                .values(
                    target_id=user_id,
                    accepted=True,
                    accepted_at=datetime.utcnow(),
                )
            )

        await session.commit()

        return True

    async def get_stats(
        self,
        tenant_id: str,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Get sharing statistics."""
        session = await self._get_session()

        conditions = [
            ShareModel.tenant_id == tenant_id,
            ShareModel.active == True,
        ]

        if user_id:
            conditions.append(ShareModel.shared_by == user_id)

        # Total shares
        total_result = await session.execute(
            select(func.count())
            .select_from(ShareModel)
            .where(and_(*conditions))
        )
        total = total_result.scalar()

        # By type
        type_result = await session.execute(
            select(ShareModel.share_type, func.count())
            .where(and_(*conditions))
            .group_by(ShareModel.share_type)
        )
        by_type = {row[0]: row[1] for row in type_result}

        # By permission
        perm_result = await session.execute(
            select(ShareModel.permission, func.count())
            .where(and_(*conditions))
            .group_by(ShareModel.permission)
        )
        by_permission = {row[0]: row[1] for row in perm_result}

        # Pending invitations
        pending_result = await session.execute(
            select(func.count())
            .select_from(ShareInvitationModel)
            .where(
                and_(
                    ShareInvitationModel.tenant_id == tenant_id,
                    ShareInvitationModel.status == "pending",
                )
            )
        )
        pending = pending_result.scalar()

        return {
            "total_shared": total,
            "by_type": by_type,
            "by_permission": by_permission,
            "pending_invitations": pending,
        }
```

### Step 3: Sharing Service

```python
# services/agent-service/src/aswa_agents/services/sharing_service.py
"""Sharing service for agents and templates."""

from typing import Any
from uuid import UUID

import structlog

from aswa_agents.models.sharing import (
    ShareRequest,
    ShareType,
    SharePermission,
    ResourceType,
    ShareInvitation,
    BulkShareRequest,
)
from aswa_agents.repositories.sharing_repository import SharingRepository
from aswa_agents.repositories.agent_repository import AgentRepository
from aswa_agents.repositories.template_repository import TemplateRepository

logger = structlog.get_logger()


class SharingService:
    """
    Service for managing agent and template sharing.

    Handles sharing, invitations, and access control.
    """

    def __init__(self):
        self._repo = SharingRepository()
        self._agent_repo = AgentRepository()
        self._template_repo = TemplateRepository()
        self._logger = logger.bind(component="SharingService")

    async def share_resource(
        self,
        tenant_id: str,
        request: ShareRequest,
        shared_by: str,
    ) -> dict[str, Any]:
        """Share a resource."""
        # Get resource name
        resource_name = await self._get_resource_name(
            request.resource_type,
            request.resource_id,
            tenant_id,
        )

        if not resource_name:
            raise ValueError("Resource not found")

        # Get target name
        target_name = await self._get_target_name(
            request.share_type,
            request.target_id,
        )

        share = await self._repo.create_share(
            tenant_id=tenant_id,
            request=request,
            resource_name=resource_name,
            target_name=target_name,
            shared_by=shared_by,
        )

        # Send notification if user share
        if request.share_type == ShareType.USER and request.target_id:
            await self._send_share_notification(
                share_id=share.id,
                target_id=request.target_id,
                resource_name=resource_name,
                shared_by=shared_by,
                message=request.message,
            )

        self._logger.info(
            "Resource shared",
            share_id=str(share.id),
            resource_type=request.resource_type.value,
            share_type=request.share_type.value,
        )

        return self._to_response(share)

    async def share_with_email(
        self,
        tenant_id: str,
        resource_type: ResourceType,
        resource_id: UUID,
        invitation: ShareInvitation,
        shared_by: str,
    ) -> dict[str, Any]:
        """Share with a user by email."""
        # Get resource name
        resource_name = await self._get_resource_name(
            resource_type,
            resource_id,
            tenant_id,
        )

        if not resource_name:
            raise ValueError("Resource not found")

        # Check if user exists
        user_id = await self._lookup_user_by_email(invitation.email)

        # Create share
        request = ShareRequest(
            resource_type=resource_type,
            resource_id=resource_id,
            share_type=ShareType.USER,
            target_id=user_id,  # May be None if user doesn't exist
            permission=invitation.permission,
            message=invitation.message,
        )

        share = await self._repo.create_share(
            tenant_id=tenant_id,
            request=request,
            resource_name=resource_name,
            target_name=invitation.email,
            shared_by=shared_by,
        )

        # Create invitation if user doesn't exist
        if not user_id:
            invite = await self._repo.create_invitation(
                tenant_id=tenant_id,
                share_id=share.id,
                email=invitation.email,
            )

            # Send invitation email
            await self._send_invitation_email(
                email=invitation.email,
                token=invite.token,
                resource_name=resource_name,
                shared_by=shared_by,
                message=invitation.message,
            )

            return {
                **self._to_response(share),
                "invitation_sent": True,
            }

        return self._to_response(share)

    async def bulk_share(
        self,
        tenant_id: str,
        request: BulkShareRequest,
        shared_by: str,
    ) -> list[dict[str, Any]]:
        """Share with multiple targets at once."""
        results = []

        for share_request in request.shares:
            try:
                if isinstance(share_request, ShareInvitation):
                    result = await self.share_with_email(
                        tenant_id=tenant_id,
                        resource_type=request.resource_type,
                        resource_id=request.resource_id,
                        invitation=share_request,
                        shared_by=shared_by,
                    )
                else:
                    share_request.resource_type = request.resource_type
                    share_request.resource_id = request.resource_id
                    result = await self.share_resource(
                        tenant_id=tenant_id,
                        request=share_request,
                        shared_by=shared_by,
                    )
                results.append({"success": True, **result})
            except Exception as e:
                results.append({
                    "success": False,
                    "error": str(e),
                    "target": share_request.target_id if hasattr(share_request, 'target_id') else share_request.email,
                })

        return results

    async def get_resource_shares(
        self,
        tenant_id: str,
        resource_type: str,
        resource_id: UUID,
    ) -> list[dict[str, Any]]:
        """Get all shares for a resource."""
        shares = await self._repo.list_resource_shares(
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
        )

        return [self._to_response(s) for s in shares]

    async def get_shared_with_me(
        self,
        tenant_id: str,
        user_id: str,
        user_teams: list[str] | None = None,
        user_roles: list[str] | None = None,
        resource_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get resources shared with current user."""
        shares = await self._repo.list_shared_with_user(
            tenant_id=tenant_id,
            user_id=user_id,
            user_teams=user_teams,
            user_roles=user_roles,
            resource_type=resource_type,
        )

        return [
            {
                "share_id": str(s.id),
                "resource_type": s.resource_type,
                "resource_id": str(s.resource_id),
                "resource_name": s.resource_name,
                "permission": s.permission,
                "shared_by": s.shared_by,
                "shared_by_name": None,  # TODO: Lookup user name
                "shared_at": s.created_at.isoformat(),
                "message": s.message,
            }
            for s in shares
        ]

    async def check_access(
        self,
        tenant_id: str,
        resource_type: str,
        resource_id: UUID,
        user_id: str,
        required_permission: SharePermission = SharePermission.VIEW,
    ) -> dict[str, Any]:
        """Check if user has access to resource."""
        # First check if user owns the resource
        is_owner = await self._check_ownership(
            resource_type,
            resource_id,
            user_id,
            tenant_id,
        )

        if is_owner:
            return {
                "has_access": True,
                "permission": SharePermission.ADMIN.value,
                "reason": "owner",
            }

        # Check shares
        has_access, permission = await self._repo.check_access(
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            required_permission=required_permission,
        )

        return {
            "has_access": has_access,
            "permission": permission,
            "reason": "shared" if has_access else "no_access",
        }

    async def revoke_share(
        self,
        tenant_id: str,
        share_id: UUID,
        user_id: str,
    ) -> bool:
        """Revoke a share."""
        # Verify user can revoke
        share = await self._repo.get_by_id(share_id, tenant_id)
        if not share:
            return False

        # Only owner or sharer can revoke
        is_owner = await self._check_ownership(
            share.resource_type,
            share.resource_id,
            user_id,
            tenant_id,
        )

        if not is_owner and share.shared_by != user_id:
            raise ValueError("Not authorized to revoke this share")

        return await self._repo.revoke_share(share_id, tenant_id)

    async def accept_share(
        self,
        share_id: UUID,
        user_id: str,
    ) -> bool:
        """Accept a pending share."""
        return await self._repo.accept_share(share_id, user_id)

    async def decline_share(
        self,
        share_id: UUID,
        user_id: str,
    ) -> bool:
        """Decline a pending share."""
        return await self._repo.decline_share(share_id, user_id)

    async def accept_invitation(
        self,
        token: str,
        user_id: str,
    ) -> dict[str, Any]:
        """Accept an invitation by token."""
        invitation = await self._repo.get_invitation_by_token(token)

        if not invitation:
            raise ValueError("Invalid or expired invitation")

        await self._repo.accept_invitation(invitation.id, user_id)

        # Get share details
        share = await self._repo.get_by_id(invitation.share_id, invitation.tenant_id)

        return {
            "accepted": True,
            "resource_type": share.resource_type,
            "resource_id": str(share.resource_id),
            "resource_name": share.resource_name,
        }

    async def get_pending_shares(
        self,
        tenant_id: str,
        user_id: str,
    ) -> list[dict[str, Any]]:
        """Get pending share requests for user."""
        session = await self._repo._get_session()

        from sqlalchemy import select, and_
        from aswa_agents.models.sharing import ShareModel, ShareType

        result = await session.execute(
            select(ShareModel).where(
                and_(
                    ShareModel.tenant_id == tenant_id,
                    ShareModel.share_type == ShareType.USER.value,
                    ShareModel.target_id == user_id,
                    ShareModel.active == True,
                    ShareModel.accepted == None,
                )
            )
        )

        shares = result.scalars().all()

        return [self._to_response(s) for s in shares]

    async def get_stats(
        self,
        tenant_id: str,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Get sharing statistics."""
        return await self._repo.get_stats(tenant_id, user_id)

    async def _get_resource_name(
        self,
        resource_type: ResourceType,
        resource_id: UUID,
        tenant_id: str,
    ) -> str | None:
        """Get resource display name."""
        if resource_type == ResourceType.AGENT:
            agent = await self._agent_repo.get_by_id(str(resource_id))
            return agent.name if agent else None
        elif resource_type == ResourceType.TEMPLATE:
            template = await self._template_repo.get_by_id(resource_id, tenant_id)
            return template.display_name if template else None
        return None

    async def _get_target_name(
        self,
        share_type: ShareType,
        target_id: str | None,
    ) -> str | None:
        """Get target display name."""
        if not target_id:
            return None
        # TODO: Implement user/team lookup
        return target_id

    async def _check_ownership(
        self,
        resource_type: str,
        resource_id: UUID,
        user_id: str,
        tenant_id: str,
    ) -> bool:
        """Check if user owns the resource."""
        if resource_type == ResourceType.AGENT.value:
            agent = await self._agent_repo.get_by_id(str(resource_id))
            return agent and agent.created_by == user_id
        elif resource_type == ResourceType.TEMPLATE.value:
            template = await self._template_repo.get_by_id(resource_id, tenant_id)
            return template and template.created_by == user_id
        return False

    async def _lookup_user_by_email(self, email: str) -> str | None:
        """Lookup user ID by email."""
        # TODO: Implement user service lookup
        return None

    async def _send_share_notification(
        self,
        share_id: UUID,
        target_id: str,
        resource_name: str,
        shared_by: str,
        message: str | None,
    ) -> None:
        """Send notification about new share."""
        # TODO: Implement notification service integration
        self._logger.info(
            "Share notification",
            share_id=str(share_id),
            target_id=target_id,
        )

    async def _send_invitation_email(
        self,
        email: str,
        token: str,
        resource_name: str,
        shared_by: str,
        message: str | None,
    ) -> None:
        """Send invitation email."""
        # TODO: Implement email service integration
        self._logger.info(
            "Invitation email",
            email=email,
            token=token[:8] + "...",
        )

    def _to_response(self, share) -> dict[str, Any]:
        """Convert share to response."""
        return {
            "id": str(share.id),
            "resource_type": share.resource_type,
            "resource_id": str(share.resource_id),
            "resource_name": share.resource_name,
            "share_type": share.share_type,
            "target_id": share.target_id,
            "target_name": share.target_name,
            "permission": share.permission,
            "shared_by": share.shared_by,
            "message": share.message,
            "active": share.active,
            "accepted": share.accepted,
            "created_at": share.created_at.isoformat(),
            "expires_at": share.expires_at.isoformat() if share.expires_at else None,
        }
```

### Step 4: Sharing API Endpoints

```python
# services/agent-service/src/aswa_agents/api/sharing.py
"""API endpoints for sharing."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aswa_agents.models.sharing import (
    ShareRequest,
    SharePermission,
    ResourceType,
    ShareInvitation,
    BulkShareRequest,
)
from aswa_agents.services.sharing_service import SharingService

router = APIRouter(prefix="/shares", tags=["sharing"])


class ShareResourceRequest(BaseModel):
    """Request to share a resource."""

    share_type: str
    target_id: str | None = None
    permission: SharePermission = SharePermission.VIEW
    message: str | None = None


class ShareWithEmailRequest(BaseModel):
    """Request to share via email."""

    email: str
    permission: SharePermission = SharePermission.VIEW
    message: str | None = None


class AccessCheckResponse(BaseModel):
    """Response for access check."""

    has_access: bool
    permission: str | None
    reason: str


@router.post("/{resource_type}/{resource_id}")
async def share_resource(
    resource_type: ResourceType,
    resource_id: UUID,
    request: ShareResourceRequest,
) -> dict[str, Any]:
    """Share a resource."""
    tenant_id = "default-tenant"
    user_id = "current-user"

    service = SharingService()

    share_request = ShareRequest(
        resource_type=resource_type,
        resource_id=resource_id,
        share_type=request.share_type,
        target_id=request.target_id,
        permission=request.permission,
        message=request.message,
    )

    try:
        return await service.share_resource(tenant_id, share_request, user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{resource_type}/{resource_id}/email")
async def share_with_email(
    resource_type: ResourceType,
    resource_id: UUID,
    request: ShareWithEmailRequest,
) -> dict[str, Any]:
    """Share with a user by email."""
    tenant_id = "default-tenant"
    user_id = "current-user"

    service = SharingService()

    invitation = ShareInvitation(
        email=request.email,
        permission=request.permission,
        message=request.message,
    )

    try:
        return await service.share_with_email(
            tenant_id, resource_type, resource_id, invitation, user_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bulk")
async def bulk_share(request: BulkShareRequest) -> dict[str, Any]:
    """Share with multiple targets."""
    tenant_id = "default-tenant"
    user_id = "current-user"

    service = SharingService()
    results = await service.bulk_share(tenant_id, request, user_id)

    return {
        "results": results,
        "success_count": len([r for r in results if r.get("success")]),
        "failure_count": len([r for r in results if not r.get("success")]),
    }


@router.get("/{resource_type}/{resource_id}")
async def get_resource_shares(
    resource_type: ResourceType,
    resource_id: UUID,
) -> dict[str, Any]:
    """Get all shares for a resource."""
    tenant_id = "default-tenant"

    service = SharingService()
    shares = await service.get_resource_shares(
        tenant_id, resource_type.value, resource_id
    )

    return {"shares": shares, "count": len(shares)}


@router.get("/with-me")
async def get_shared_with_me(
    resource_type: ResourceType | None = None,
) -> dict[str, Any]:
    """Get resources shared with current user."""
    tenant_id = "default-tenant"
    user_id = "current-user"

    service = SharingService()
    shares = await service.get_shared_with_me(
        tenant_id,
        user_id,
        resource_type=resource_type.value if resource_type else None,
    )

    return {"shares": shares, "count": len(shares)}


@router.get("/pending")
async def get_pending_shares() -> dict[str, Any]:
    """Get pending share requests."""
    tenant_id = "default-tenant"
    user_id = "current-user"

    service = SharingService()
    shares = await service.get_pending_shares(tenant_id, user_id)

    return {"shares": shares, "count": len(shares)}


@router.get("/{resource_type}/{resource_id}/access")
async def check_access(
    resource_type: ResourceType,
    resource_id: UUID,
    permission: SharePermission = SharePermission.VIEW,
) -> AccessCheckResponse:
    """Check if current user has access."""
    tenant_id = "default-tenant"
    user_id = "current-user"

    service = SharingService()
    result = await service.check_access(
        tenant_id,
        resource_type.value,
        resource_id,
        user_id,
        permission,
    )

    return AccessCheckResponse(**result)


@router.delete("/{share_id}")
async def revoke_share(share_id: UUID) -> dict[str, Any]:
    """Revoke a share."""
    tenant_id = "default-tenant"
    user_id = "current-user"

    service = SharingService()

    try:
        success = await service.revoke_share(tenant_id, share_id, user_id)
        if not success:
            raise HTTPException(status_code=404, detail="Share not found")
        return {"revoked": True}
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/{share_id}/accept")
async def accept_share(share_id: UUID) -> dict[str, Any]:
    """Accept a pending share."""
    user_id = "current-user"

    service = SharingService()
    success = await service.accept_share(share_id, user_id)

    if not success:
        raise HTTPException(status_code=404, detail="Share not found")

    return {"accepted": True}


@router.post("/{share_id}/decline")
async def decline_share(share_id: UUID) -> dict[str, Any]:
    """Decline a pending share."""
    user_id = "current-user"

    service = SharingService()
    success = await service.decline_share(share_id, user_id)

    if not success:
        raise HTTPException(status_code=404, detail="Share not found")

    return {"declined": True}


@router.post("/invitations/{token}/accept")
async def accept_invitation(token: str) -> dict[str, Any]:
    """Accept an invitation by token."""
    user_id = "current-user"

    service = SharingService()

    try:
        return await service.accept_invitation(token, user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/stats")
async def get_share_stats() -> dict[str, Any]:
    """Get sharing statistics."""
    tenant_id = "default-tenant"
    user_id = "current-user"

    service = SharingService()
    return await service.get_stats(tenant_id, user_id)
```

## Test Cases

```python
# services/agent-service/tests/unit/test_sharing.py
"""Tests for agent sharing."""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, patch, MagicMock

from aswa_agents.models.sharing import (
    ShareRequest,
    ShareType,
    SharePermission,
    ResourceType,
)
from aswa_agents.services.sharing_service import SharingService
from aswa_agents.repositories.sharing_repository import SharingRepository


class TestSharingRepository:
    """Test SharingRepository."""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_create_share(self, mock_session):
        """Test creating a share."""
        repo = SharingRepository(session=mock_session)

        request = ShareRequest(
            resource_type=ResourceType.AGENT,
            resource_id=uuid4(),
            share_type=ShareType.USER,
            target_id="user-123",
            permission=SharePermission.VIEW,
        )

        mock_session.execute.return_value = AsyncMock(
            scalar_one_or_none=lambda: None
        )

        await repo.create_share(
            tenant_id="test",
            request=request,
            resource_name="Test Agent",
            target_name="John Doe",
            shared_by="admin",
        )

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_list_shared_with_user(self, mock_session):
        """Test listing resources shared with user."""
        repo = SharingRepository(session=mock_session)

        mock_share = MagicMock()
        mock_share.id = uuid4()
        mock_share.resource_type = "agent"
        mock_share.resource_id = uuid4()
        mock_share.share_type = ShareType.USER.value
        mock_share.target_id = "user-123"
        mock_share.permission = SharePermission.VIEW.value
        mock_share.active = True
        mock_share.accepted = True

        mock_session.execute.return_value = AsyncMock(
            scalars=lambda: AsyncMock(all=lambda: [mock_share])
        )

        shares = await repo.list_shared_with_user(
            tenant_id="test",
            user_id="user-123",
        )

        assert len(shares) == 1

    @pytest.mark.asyncio
    async def test_check_access_allowed(self, mock_session):
        """Test checking access when allowed."""
        repo = SharingRepository(session=mock_session)

        mock_share = MagicMock()
        mock_share.resource_id = uuid4()
        mock_share.permission = SharePermission.VIEW.value

        with patch.object(repo, "list_shared_with_user") as mock_list:
            mock_list.return_value = [mock_share]

            allowed, permission = await repo.check_access(
                tenant_id="test",
                resource_type="agent",
                resource_id=mock_share.resource_id,
                user_id="user-123",
                required_permission=SharePermission.VIEW,
            )

            assert allowed is True
            assert permission == SharePermission.VIEW.value

    @pytest.mark.asyncio
    async def test_check_access_denied(self, mock_session):
        """Test checking access when denied."""
        repo = SharingRepository(session=mock_session)

        with patch.object(repo, "list_shared_with_user") as mock_list:
            mock_list.return_value = []

            allowed, reason = await repo.check_access(
                tenant_id="test",
                resource_type="agent",
                resource_id=uuid4(),
                user_id="user-123",
            )

            assert allowed is False
            assert reason == "No share found"


class TestSharingService:
    """Test SharingService."""

    @pytest.fixture
    def service(self):
        return SharingService()

    @pytest.mark.asyncio
    async def test_share_resource(self, service):
        """Test sharing a resource."""
        request = ShareRequest(
            resource_type=ResourceType.AGENT,
            resource_id=uuid4(),
            share_type=ShareType.USER,
            target_id="user-123",
            permission=SharePermission.VIEW,
        )

        mock_share = MagicMock()
        mock_share.id = uuid4()
        mock_share.resource_type = "agent"
        mock_share.resource_id = request.resource_id
        mock_share.resource_name = "Test Agent"
        mock_share.share_type = ShareType.USER.value
        mock_share.target_id = "user-123"
        mock_share.target_name = "John"
        mock_share.permission = SharePermission.VIEW.value
        mock_share.shared_by = "admin"
        mock_share.message = None
        mock_share.active = True
        mock_share.accepted = None
        mock_share.created_at = datetime.utcnow()
        mock_share.expires_at = None

        with patch.object(service, "_get_resource_name") as mock_name:
            mock_name.return_value = "Test Agent"

            with patch.object(service._repo, "create_share") as mock_create:
                mock_create.return_value = mock_share

                with patch.object(service, "_send_share_notification"):
                    result = await service.share_resource(
                        "test", request, "admin"
                    )

                    assert result["resource_name"] == "Test Agent"
                    mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_access_owner(self, service):
        """Test that owner always has access."""
        resource_id = uuid4()

        with patch.object(service, "_check_ownership") as mock_owner:
            mock_owner.return_value = True

            result = await service.check_access(
                tenant_id="test",
                resource_type="agent",
                resource_id=resource_id,
                user_id="owner-123",
            )

            assert result["has_access"] is True
            assert result["permission"] == SharePermission.ADMIN.value
            assert result["reason"] == "owner"

    @pytest.mark.asyncio
    async def test_check_access_shared(self, service):
        """Test checking access for shared resource."""
        resource_id = uuid4()

        with patch.object(service, "_check_ownership") as mock_owner:
            mock_owner.return_value = False

            with patch.object(service._repo, "check_access") as mock_check:
                mock_check.return_value = (True, SharePermission.EDIT.value)

                result = await service.check_access(
                    tenant_id="test",
                    resource_type="agent",
                    resource_id=resource_id,
                    user_id="user-123",
                )

                assert result["has_access"] is True
                assert result["permission"] == SharePermission.EDIT.value
                assert result["reason"] == "shared"

    @pytest.mark.asyncio
    async def test_revoke_share_not_authorized(self, service):
        """Test that non-owner cannot revoke share."""
        share_id = uuid4()

        mock_share = MagicMock()
        mock_share.resource_type = "agent"
        mock_share.resource_id = uuid4()
        mock_share.shared_by = "other-user"

        with patch.object(service._repo, "get_by_id") as mock_get:
            mock_get.return_value = mock_share

            with patch.object(service, "_check_ownership") as mock_owner:
                mock_owner.return_value = False

                with pytest.raises(ValueError) as exc:
                    await service.revoke_share(
                        "test", share_id, "unauthorized-user"
                    )

                assert "Not authorized" in str(exc.value)


class TestShareTypes:
    """Test different share types."""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_team_share(self, mock_session):
        """Test sharing with a team."""
        repo = SharingRepository(session=mock_session)

        request = ShareRequest(
            resource_type=ResourceType.AGENT,
            resource_id=uuid4(),
            share_type=ShareType.TEAM,
            target_id="team-engineering",
            permission=SharePermission.EDIT,
        )

        mock_session.execute.return_value = AsyncMock(
            scalar_one_or_none=lambda: None
        )

        await repo.create_share(
            tenant_id="test",
            request=request,
            resource_name="Test Agent",
            target_name="Engineering Team",
            shared_by="admin",
        )

        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_tenant_wide_share(self, mock_session):
        """Test tenant-wide sharing."""
        repo = SharingRepository(session=mock_session)

        request = ShareRequest(
            resource_type=ResourceType.TEMPLATE,
            resource_id=uuid4(),
            share_type=ShareType.TENANT,
            permission=SharePermission.VIEW,
        )

        mock_session.execute.return_value = AsyncMock(
            scalar_one_or_none=lambda: None
        )

        await repo.create_share(
            tenant_id="test",
            request=request,
            resource_name="Email Template",
            target_name=None,
            shared_by="admin",
        )

        mock_session.add.assert_called_once()


class TestShareInvitations:
    """Test share invitations."""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_create_invitation(self, mock_session):
        """Test creating an invitation."""
        repo = SharingRepository(session=mock_session)

        invitation = await repo.create_invitation(
            tenant_id="test",
            share_id=uuid4(),
            email="newuser@example.com",
        )

        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_accept_invitation(self, mock_session):
        """Test accepting an invitation."""
        repo = SharingRepository(session=mock_session)
        invitation_id = uuid4()

        mock_invitation = MagicMock()
        mock_invitation.id = invitation_id
        mock_invitation.share_id = uuid4()

        mock_session.execute.return_value = AsyncMock(
            scalar_one_or_none=lambda: mock_invitation
        )

        result = await repo.accept_invitation(invitation_id, "user-123")

        assert result is True
        mock_session.commit.assert_called()
```

## Verification Steps

1. **Run unit tests:**
   ```bash
   cd services/agent-service
   pytest tests/unit/test_sharing.py -v
   ```

2. **Test sharing API:**
   ```bash
   # Share with user
   curl -X POST http://localhost:8000/api/v1/shares/agent/{id} \
     -H "Content-Type: application/json" \
     -d '{
       "share_type": "user",
       "target_id": "user-123",
       "permission": "view"
     }'

   # Share with email
   curl -X POST http://localhost:8000/api/v1/shares/agent/{id}/email \
     -H "Content-Type: application/json" \
     -d '{
       "email": "colleague@example.com",
       "permission": "edit"
     }'

   # Get shared with me
   curl http://localhost:8000/api/v1/shares/with-me

   # Check access
   curl http://localhost:8000/api/v1/shares/agent/{id}/access
   ```

3. **Test access control:**
   - Share resource with different permissions
   - Verify access levels work correctly
   - Test owner override behavior

4. **Test invitations:**
   - Create invitation for non-existent user
   - Accept invitation via token
   - Verify share is updated

## Next Task

Proceed to `task-9.8.1-trigger-connectors.md` for implementing trigger connectors.
