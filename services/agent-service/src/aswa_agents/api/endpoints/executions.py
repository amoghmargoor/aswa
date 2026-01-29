"""Execution history endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def list_executions():
    """List executions for tenant."""
    # Implementation in Task 9.5.2
    return {"message": "Not implemented"}


@router.get("/{execution_id}")
async def get_execution(execution_id: str):
    """Get execution details."""
    # Implementation in Task 9.5.2
    return {"message": "Not implemented"}
