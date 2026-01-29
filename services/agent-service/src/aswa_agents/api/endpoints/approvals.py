"""Approval workflow endpoints."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from aswa_agents.api.dependencies import get_current_tenant
from aswa_agents.governance import (
    AccessControl,
    ApprovalAction,
    ApprovalPolicy,
    ApprovalRequest,
    ApprovalStatus,
    ApprovalWorkflow,
    Permission,
    Role,
)

router = APIRouter()


class ApprovalRequestResponse(BaseModel):
    """Response model for approval requests."""

    id: UUID
    agent_id: UUID
    action: str
    status: str
    requester_id: UUID
    details: dict[str, Any]
    required_approvers: int
    current_approvals: int
    created_at: str


class ApprovalListResponse(BaseModel):
    """Response model for approval list."""

    approvals: list[ApprovalRequestResponse]
    total: int


class CreatePolicyRequest(BaseModel):
    """Request model for creating an approval policy."""

    name: str
    description: str = ""
    action: ApprovalAction
    required_approvers: int = 1
    allowed_approver_roles: list[str] = Field(default_factory=list)
    auto_approve_conditions: dict[str, Any] | None = None


class RoleRequest(BaseModel):
    """Request model for role operations."""

    name: str
    display_name: str
    description: str = ""
    permissions: list[Permission]


def _approval_to_response(approval: ApprovalRequest) -> ApprovalRequestResponse:
    """Convert approval request to response model."""
    return ApprovalRequestResponse(
        id=approval.id,
        agent_id=approval.agent_id,
        action=approval.action.value,
        status=approval.status.value,
        requester_id=approval.requester_id,
        details=approval.details,
        required_approvers=approval.required_approvers,
        current_approvals=len(approval.approvals),
        created_at=approval.created_at.isoformat(),
    )


@router.get("", response_model=ApprovalListResponse)
async def list_pending_approvals(
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    user_id: str = Query(..., description="User ID"),
    status: ApprovalStatus | None = Query(None, description="Filter by status"),
):
    """List pending approvals for tenant."""
    workflow = ApprovalWorkflow(UUID(tenant_id))

    # Get pending approvals for this user
    approvals = await workflow.get_pending_for_user(UUID(user_id))

    # Filter by status if specified
    if status:
        approvals = [a for a in approvals if a.status == status]

    return ApprovalListResponse(
        approvals=[_approval_to_response(a) for a in approvals],
        total=len(approvals),
    )


@router.get("/{approval_id}")
async def get_approval(
    approval_id: UUID,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
):
    """Get approval request details."""
    workflow = ApprovalWorkflow(UUID(tenant_id))

    approval = await workflow.get_request(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval request not found")

    return _approval_to_response(approval)


@router.post("/{approval_id}/approve")
async def approve_action(
    approval_id: UUID,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    user_id: str = Query(..., description="User ID"),
    comment: str = Query("", description="Optional comment"),
):
    """Approve a pending action."""
    workflow = ApprovalWorkflow(UUID(tenant_id))

    try:
        approval = await workflow.approve(approval_id, UUID(user_id), comment)
        return {
            "id": str(approval.id),
            "status": approval.status.value,
            "message": "Approval recorded",
            "is_complete": approval.status == ApprovalStatus.APPROVED,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/{approval_id}/reject")
async def reject_action(
    approval_id: UUID,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    user_id: str = Query(..., description="User ID"),
    reason: str = Query(..., description="Rejection reason"),
):
    """Reject a pending action."""
    workflow = ApprovalWorkflow(UUID(tenant_id))

    try:
        approval = await workflow.reject(approval_id, UUID(user_id), reason)
        return {
            "id": str(approval.id),
            "status": approval.status.value,
            "message": "Action rejected",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


# Policy management endpoints

@router.get("/policies")
async def list_policies(
    tenant_id: Annotated[str, Depends(get_current_tenant)],
):
    """List approval policies."""
    workflow = ApprovalWorkflow(UUID(tenant_id))

    policies = await workflow.get_policies()

    return {
        "policies": [
            {
                "id": str(p.id),
                "name": p.name,
                "description": p.description,
                "action": p.action.value,
                "required_approvers": p.required_approvers,
                "is_active": p.is_active,
            }
            for p in policies
        ]
    }


@router.post("/policies", status_code=201)
async def create_policy(
    request: CreatePolicyRequest,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
):
    """Create an approval policy."""
    workflow = ApprovalWorkflow(UUID(tenant_id))

    policy = ApprovalPolicy(
        name=request.name,
        description=request.description,
        action=request.action,
        required_approvers=request.required_approvers,
        allowed_approver_roles=request.allowed_approver_roles,
        auto_approve_conditions=request.auto_approve_conditions,
    )

    created = await workflow.create_policy(policy)

    return {
        "id": str(created.id),
        "name": created.name,
        "action": created.action.value,
    }


@router.delete("/policies/{policy_id}", status_code=204)
async def delete_policy(
    policy_id: UUID,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
):
    """Delete an approval policy."""
    workflow = ApprovalWorkflow(UUID(tenant_id))

    try:
        await workflow.delete_policy(policy_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# Role management endpoints

@router.get("/roles")
async def list_roles(
    tenant_id: Annotated[str, Depends(get_current_tenant)],
):
    """List roles."""
    access_control = AccessControl(UUID(tenant_id))

    roles = await access_control.get_roles()

    return {
        "roles": [
            {
                "id": str(r.id),
                "name": r.name,
                "display_name": r.display_name,
                "description": r.description,
                "permissions": [p.value for p in r.permissions],
                "is_system": r.is_system,
            }
            for r in roles
        ]
    }


@router.post("/roles", status_code=201)
async def create_role(
    request: RoleRequest,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
):
    """Create a custom role."""
    access_control = AccessControl(UUID(tenant_id))

    role = Role(
        name=request.name,
        display_name=request.display_name,
        description=request.description,
        permissions=request.permissions,
        is_system=False,
    )

    created = await access_control.create_role(role)

    return {
        "id": str(created.id),
        "name": created.name,
        "permissions": [p.value for p in created.permissions],
    }


@router.get("/users/{user_id}/permissions")
async def get_user_permissions(
    user_id: UUID,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
):
    """Get permissions for a user."""
    access_control = AccessControl(UUID(tenant_id))

    permissions = await access_control.get_user_permissions(user_id)

    return {
        "user_id": str(user_id),
        "permissions": [p.value for p in permissions],
    }


@router.post("/users/{user_id}/roles/{role_id}")
async def assign_role(
    user_id: UUID,
    role_id: UUID,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
):
    """Assign a role to a user."""
    access_control = AccessControl(UUID(tenant_id))

    try:
        await access_control.assign_role(user_id, role_id)
        return {"message": "Role assigned successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/users/{user_id}/roles/{role_id}", status_code=204)
async def remove_role(
    user_id: UUID,
    role_id: UUID,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
):
    """Remove a role from a user."""
    access_control = AccessControl(UUID(tenant_id))

    try:
        await access_control.remove_role(user_id, role_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/check")
async def check_permission(
    user_id: str = Query(..., description="User ID"),
    permission: Permission = Query(..., description="Permission to check"),
    resource_id: str | None = Query(None, description="Optional resource ID"),
    tenant_id: Annotated[str, Depends(get_current_tenant)] = None,
):
    """Check if a user has a specific permission."""
    access_control = AccessControl(UUID(tenant_id))

    has_permission = await access_control.check_permission(
        user_id=UUID(user_id),
        permission=permission,
        resource_id=UUID(resource_id) if resource_id else None,
    )

    return {
        "user_id": user_id,
        "permission": permission.value,
        "allowed": has_permission,
    }
