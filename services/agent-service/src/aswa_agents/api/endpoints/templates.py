"""Template management endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def list_templates():
    """List available agent templates."""
    # Implementation in Task 9.7.1
    return {"message": "Not implemented"}


@router.get("/{template_id}")
async def get_template(template_id: str):
    """Get template details."""
    # Implementation in Task 9.7.1
    return {"message": "Not implemented"}


@router.post("/{template_id}/instantiate")
async def instantiate_template(template_id: str):
    """Create an agent from a template."""
    # Implementation in Task 9.7.1
    return {"message": "Not implemented"}
