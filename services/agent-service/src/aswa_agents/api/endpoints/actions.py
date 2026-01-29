"""Action block endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def list_action_blocks():
    """List available action blocks."""
    # Implementation in Task 9.4.4
    return {"message": "Not implemented"}


@router.get("/{block_id}")
async def get_action_block(block_id: str):
    """Get action block details."""
    # Implementation in Task 9.4.4
    return {"message": "Not implemented"}


@router.get("/{block_id}/schema")
async def get_action_block_schema(block_id: str):
    """Get action block configuration schema."""
    # Implementation in Task 9.4.4
    return {"message": "Not implemented"}
