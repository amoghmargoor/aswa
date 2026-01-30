"""Template management endpoints."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from aswa_agents.api.dependencies import get_current_tenant, get_db_session
from aswa_agents.templates import (
    AgentTemplate,
    TemplateCategory,
    TemplateEngine,
    TemplateLibrary,
    TemplateVariable,
)

router = APIRouter()


class TemplateResponse(BaseModel):
    """Response model for templates."""

    id: UUID
    name: str
    display_name: str
    description: str
    category: str
    visibility: str
    icon: str
    tags: list[str]
    use_count: int
    rating: float
    rating_count: int
    variables: list[dict[str, Any]]


class TemplateListResponse(BaseModel):
    """Response model for template list."""

    templates: list[TemplateResponse]
    total: int


class InstantiateRequest(BaseModel):
    """Request model for template instantiation."""

    name: str = Field(..., description="Name for the new agent")
    display_name: str = Field(..., description="Display name for the new agent")
    description: str = Field("", description="Description for the new agent")
    variables: dict[str, Any] = Field(default_factory=dict, description="Variable values")


class CreateTemplateRequest(BaseModel):
    """Request model for creating a template."""

    name: str
    display_name: str
    description: str
    category: TemplateCategory
    icon: str = "zap"
    tags: list[str] = Field(default_factory=list)
    definition: dict[str, Any] = Field(default_factory=dict)
    variables: list[dict[str, Any]] = Field(default_factory=list)


class PreviewResponse(BaseModel):
    """Response model for template preview."""

    definition: dict[str, Any]
    variables_used: list[str]


def _template_to_response(template: AgentTemplate) -> TemplateResponse:
    """Convert template to response model."""
    return TemplateResponse(
        id=template.id,
        name=template.name,
        display_name=template.display_name,
        description=template.description,
        category=template.category.value,
        visibility=template.visibility.value,
        icon=template.icon,
        tags=template.tags,
        use_count=template.use_count,
        rating=template.rating,
        rating_count=template.rating_count,
        variables=[
            {
                "name": v.name,
                "display_name": v.display_name,
                "description": v.description,
                "type": v.type,
                "required": v.required,
                "default": v.default,
                "options": v.options,
            }
            for v in template.variables
        ],
    )


@router.get("", response_model=TemplateListResponse)
async def list_templates(
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    category: TemplateCategory | None = Query(None, description="Filter by category"),
    search: str | None = Query(None, description="Search query"),
    tags: list[str] | None = Query(None, description="Filter by tags"),
) -> TemplateListResponse:
    """List available agent templates."""
    library = TemplateLibrary(UUID(tenant_id))

    templates = await library.get_templates(
        category=category,
        search=search,
        tags=tags,
    )

    return TemplateListResponse(
        templates=[_template_to_response(t) for t in templates],
        total=len(templates),
    )


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: UUID,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
) -> TemplateResponse:
    """Get template details."""
    library = TemplateLibrary(UUID(tenant_id))

    template = await library.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return _template_to_response(template)


@router.post("", response_model=TemplateResponse, status_code=201)
async def create_template(
    request: CreateTemplateRequest,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    user_id: str = Query(..., description="User ID"),
) -> TemplateResponse:
    """Create a new template."""
    library = TemplateLibrary(UUID(tenant_id))

    # Convert variable dicts to TemplateVariable objects
    variables = [
        TemplateVariable(
            name=v["name"],
            display_name=v.get("display_name", v["name"]),
            description=v.get("description", ""),
            type=v.get("type", "string"),
            required=v.get("required", True),
            default=v.get("default"),
            options=v.get("options"),
        )
        for v in request.variables
    ]

    template = AgentTemplate(
        name=request.name,
        display_name=request.display_name,
        description=request.description,
        category=request.category,
        icon=request.icon,
        tags=request.tags,
        definition=request.definition,
        variables=variables,
    )

    created = await library.create_template(template, UUID(user_id))
    return _template_to_response(created)


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: UUID,
    updates: dict[str, Any],
    tenant_id: Annotated[str, Depends(get_current_tenant)],
) -> TemplateResponse:
    """Update a template."""
    library = TemplateLibrary(UUID(tenant_id))

    try:
        updated = await library.update_template(template_id, updates)
        return _template_to_response(updated)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.delete("/{template_id}", status_code=204)
async def delete_template(
    template_id: UUID,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
) -> None:
    """Delete a template."""
    library = TemplateLibrary(UUID(tenant_id))

    try:
        await library.delete_template(template_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/{template_id}/preview", response_model=PreviewResponse)
async def preview_template(
    template_id: UUID,
    variables: dict[str, Any] | None = None,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
) -> PreviewResponse:
    """Preview template with optional variable values."""
    library = TemplateLibrary(UUID(tenant_id))
    engine = TemplateEngine()

    template = await library.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    preview = engine.preview(template, variables)

    return PreviewResponse(
        definition=preview,
        variables_used=[v.name for v in template.variables],
    )


@router.post("/{template_id}/validate")
async def validate_template_variables(
    template_id: UUID,
    variables: dict[str, Any],
    tenant_id: Annotated[str, Depends(get_current_tenant)],
):
    """Validate variable values against template schema."""
    library = TemplateLibrary(UUID(tenant_id))
    engine = TemplateEngine()

    template = await library.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    errors = engine.validate_variables(template, variables)

    return {
        "valid": len(errors) == 0,
        "errors": errors,
    }


@router.post("/{template_id}/instantiate")
async def instantiate_template(
    template_id: UUID,
    request: InstantiateRequest,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user_id: str = Query(..., description="User ID"),
):
    """Create an agent from a template."""
    from aswa_agents.api.schemas import AgentCreate
    from aswa_agents.persistence.repository import AgentRepository

    library = TemplateLibrary(UUID(tenant_id))
    engine = TemplateEngine()

    template = await library.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Validate and render
    try:
        definition = engine.render(template, request.variables)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Create agent from rendered definition
    agent_data = AgentCreate(
        name=request.name,
        display_name=request.display_name,
        description=request.description or template.description,
        trigger=definition.get("trigger", {}),
        actions=definition.get("actions", []),
        conditions=definition.get("conditions"),
    )

    repo = AgentRepository(session)
    agent = await repo.create(tenant_id=tenant_id, data=agent_data)

    # Update template use count
    await library.update_template(template_id, {"use_count": template.use_count + 1})

    return {
        "agent_id": str(agent.id),
        "template_id": str(template_id),
        "name": agent.name,
        "display_name": agent.display_name,
        "status": agent.status,
    }
