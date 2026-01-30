"""Action block endpoints."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from aswa_agents.api.dependencies import get_current_tenant
from aswa_agents.actions.blocks import ActionRegistry, ActionCategory


router = APIRouter()


class ActionBlockResponse(BaseModel):
    """Response model for action blocks."""

    id: str
    name: str
    display_name: str
    description: str
    category: str
    icon: str
    version: str


class ActionBlockListResponse(BaseModel):
    """Response model for action block list."""

    blocks: list[ActionBlockResponse]
    total: int


class ActionSchemaResponse(BaseModel):
    """Response model for action schema."""

    id: str
    name: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    config_schema: dict[str, Any]


@router.get("", response_model=ActionBlockListResponse)
async def list_action_blocks(
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    category: ActionCategory | None = None,
):
    """List available action blocks."""
    registry = ActionRegistry()

    if category:
        blocks = registry.get_by_category(category)
    else:
        blocks = registry.list_all()

    return ActionBlockListResponse(
        blocks=[
            ActionBlockResponse(
                id=block.id,
                name=block.name,
                display_name=block.display_name,
                description=block.description,
                category=block.category.value,
                icon=block.icon,
                version=block.version,
            )
            for block in blocks
        ],
        total=len(blocks),
    )


@router.get("/categories")
async def list_categories(
    tenant_id: Annotated[str, Depends(get_current_tenant)],
):
    """List action block categories."""
    return {
        "categories": [
            {
                "id": cat.value,
                "name": cat.name.replace("_", " ").title(),
                "description": _get_category_description(cat),
            }
            for cat in ActionCategory
        ]
    }


def _get_category_description(category: ActionCategory) -> str:
    """Get description for a category."""
    descriptions = {
        ActionCategory.DATA: "Actions for processing and transforming data",
        ActionCategory.INTEGRATION: "Actions for integrating with external services",
        ActionCategory.LOGIC: "Actions for flow control and conditional logic",
        ActionCategory.AI: "AI-powered actions using language models",
        ActionCategory.NOTIFICATION: "Actions for sending notifications",
        ActionCategory.CUSTOM: "Custom user-defined actions",
    }
    return descriptions.get(category, "")


@router.get("/{block_id}", response_model=ActionBlockResponse)
async def get_action_block(
    block_id: str,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
):
    """Get action block details."""
    registry = ActionRegistry()

    block = registry.get(block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Action block not found")

    return ActionBlockResponse(
        id=block.id,
        name=block.name,
        display_name=block.display_name,
        description=block.description,
        category=block.category.value,
        icon=block.icon,
        version=block.version,
    )


@router.get("/{block_id}/schema", response_model=ActionSchemaResponse)
async def get_action_block_schema(
    block_id: str,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
):
    """Get action block configuration schema."""
    registry = ActionRegistry()

    block = registry.get(block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Action block not found")

    schema = block.get_schema()

    return ActionSchemaResponse(
        id=block.id,
        name=block.name,
        input_schema=schema.input_schema,
        output_schema=schema.output_schema,
        config_schema=schema.config_schema,
    )


@router.post("/{block_id}/validate")
async def validate_action_config(
    block_id: str,
    config: dict[str, Any],
    tenant_id: Annotated[str, Depends(get_current_tenant)],
):
    """Validate action block configuration."""
    registry = ActionRegistry()

    block = registry.get(block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Action block not found")

    try:
        is_valid = block.validate_config(config)
        return {
            "valid": is_valid,
            "errors": [],
        }
    except ValueError as e:
        return {
            "valid": False,
            "errors": [str(e)],
        }


@router.post("/{block_id}/preview")
async def preview_action_execution(
    block_id: str,
    config: dict[str, Any],
    sample_input: dict[str, Any] | None = None,
    tenant_id: Annotated[str, Depends(get_current_tenant)] = None,
):
    """Preview action execution with sample data."""
    registry = ActionRegistry()

    block = registry.get(block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Action block not found")

    # Validate config first
    try:
        block.validate_config(config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid config: {e}")

    schema = block.get_schema()

    # Generate sample output based on schema
    sample_output = _generate_sample_output(schema.output_schema)

    return {
        "block_id": block_id,
        "config": config,
        "sample_input": sample_input or {},
        "expected_output_schema": schema.output_schema,
        "sample_output": sample_output,
    }


def _generate_sample_output(schema: dict[str, Any]) -> dict[str, Any]:
    """Generate sample output based on schema."""
    properties = schema.get("properties", {})
    sample = {}

    for key, prop in properties.items():
        prop_type = prop.get("type", "string")
        if prop_type == "string":
            sample[key] = f"sample_{key}"
        elif prop_type == "number":
            sample[key] = 0.0
        elif prop_type == "integer":
            sample[key] = 0
        elif prop_type == "boolean":
            sample[key] = True
        elif prop_type == "array":
            sample[key] = []
        elif prop_type == "object":
            sample[key] = {}

    return sample
