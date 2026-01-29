"""Approval workflow endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def list_pending_approvals():
    """List pending approvals for tenant."""
    # Implementation in Task 9.6.1
    return {"message": "Not implemented"}


@router.post("/{approval_id}/approve")
async def approve_action(approval_id: str):
    """Approve a pending action."""
    # Implementation in Task 9.6.1
    return {"message": "Not implemented"}


@router.post("/{approval_id}/reject")
async def reject_action(approval_id: str):
    """Reject a pending action."""
    # Implementation in Task 9.6.1
    return {"message": "Not implemented"}
