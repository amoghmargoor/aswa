"""Agent management endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from aswa_agents.api.dependencies import get_current_tenant, get_db_session
from aswa_agents.api.schemas import (
    AgentCreate,
    AgentResponse,
    AgentListResponse,
    AgentUpdate,
    TriggerRequest,
    ExecutionResponse,
)
from aswa_agents.persistence.repository import AgentRepository


router = APIRouter()


@router.post("", response_model=AgentResponse, status_code=201)
async def create_agent(
    agent_data: AgentCreate,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AgentResponse:
    """Create a new agent."""
    repo = AgentRepository(session)
    agent = await repo.create(tenant_id=tenant_id, data=agent_data)
    return AgentResponse.model_validate(agent)


@router.get("", response_model=AgentListResponse)
async def list_agents(
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> AgentListResponse:
    """List all agents for tenant."""
    repo = AgentRepository(session)
    agents, total = await repo.list(
        tenant_id=tenant_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return AgentListResponse(
        agents=[AgentResponse.model_validate(a) for a in agents],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: UUID,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AgentResponse:
    """Get agent by ID."""
    repo = AgentRepository(session)
    agent = await repo.get(agent_id=agent_id, tenant_id=tenant_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentResponse.model_validate(agent)


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: UUID,
    agent_data: AgentUpdate,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AgentResponse:
    """Update an agent."""
    repo = AgentRepository(session)
    agent = await repo.update(
        agent_id=agent_id,
        tenant_id=tenant_id,
        data=agent_data,
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentResponse.model_validate(agent)


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: UUID,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    """Delete an agent."""
    repo = AgentRepository(session)
    deleted = await repo.delete(agent_id=agent_id, tenant_id=tenant_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Agent not found")


@router.post("/{agent_id}/trigger", response_model=ExecutionResponse)
async def trigger_agent(
    agent_id: UUID,
    trigger_data: TriggerRequest,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ExecutionResponse:
    """Manually trigger an agent execution."""
    # Implementation in Task 9.1.4
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/{agent_id}/test", response_model=ExecutionResponse)
async def test_agent(
    agent_id: UUID,
    trigger_data: TriggerRequest,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ExecutionResponse:
    """Test agent with dry-run execution."""
    from aswa_agents.testing import AgentSandbox

    repo = AgentRepository(session)
    agent = await repo.get(agent_id=agent_id, tenant_id=tenant_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Convert agent to definition dict
    agent_definition = {
        "trigger": agent.trigger,
        "actions": agent.actions,
        "conditions": agent.conditions,
    }

    # Run in sandbox
    sandbox = AgentSandbox(
        agent_definition=agent_definition,
        tenant_id=UUID(tenant_id),
        mock_integrations=True,
    )

    results = await sandbox.execute(
        trigger_data=trigger_data.data,
        timeout_seconds=30,
    )

    from uuid import uuid4

    return ExecutionResponse(
        execution_id=uuid4(),
        agent_id=agent_id,
        status="completed" if all(r.status.value == "success" for r in results) else "failed",
        results=[r.model_dump() for r in results],
    )


@router.post("/{agent_id}/clone", response_model=AgentResponse)
async def clone_agent(
    agent_id: UUID,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AgentResponse:
    """Clone an existing agent."""
    repo = AgentRepository(session)
    agent = await repo.get(agent_id=agent_id, tenant_id=tenant_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Create new agent with same definition
    clone_data = AgentCreate(
        name=f"{agent.name}-copy",
        display_name=f"{agent.display_name} (Copy)",
        description=agent.description,
        trigger=agent.trigger,
        actions=agent.actions,
        conditions=agent.conditions,
    )

    new_agent = await repo.create(tenant_id=tenant_id, data=clone_data)
    return AgentResponse.model_validate(new_agent)


@router.post("/{agent_id}/activate", response_model=AgentResponse)
async def activate_agent(
    agent_id: UUID,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AgentResponse:
    """Activate an agent."""
    repo = AgentRepository(session)
    agent = await repo.update_status(
        agent_id=agent_id,
        tenant_id=tenant_id,
        status="active",
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentResponse.model_validate(agent)


@router.post("/{agent_id}/pause", response_model=AgentResponse)
async def pause_agent(
    agent_id: UUID,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AgentResponse:
    """Pause an agent."""
    repo = AgentRepository(session)
    agent = await repo.update_status(
        agent_id=agent_id,
        tenant_id=tenant_id,
        status="paused",
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentResponse.model_validate(agent)


@router.get("/{agent_id}/versions")
async def get_agent_versions(
    agent_id: UUID,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Get version history for an agent."""
    from aswa_agents.governance import VersionManager

    manager = VersionManager(UUID(tenant_id))
    versions = await manager.get_versions(agent_id)

    return {
        "versions": [
            {
                "id": str(v.id),
                "version_number": v.version_number,
                "status": v.status.value,
                "changelog": v.changelog,
                "created_at": v.created_at.isoformat(),
                "published_at": v.published_at.isoformat() if v.published_at else None,
            }
            for v in versions
        ]
    }


@router.post("/{agent_id}/versions/{version_number}/publish")
async def publish_agent_version(
    agent_id: UUID,
    version_number: int,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user_id: str = Query(..., description="User ID"),
):
    """Publish a specific version of an agent."""
    from aswa_agents.governance import VersionManager

    manager = VersionManager(UUID(tenant_id))
    version = await manager.get_version(agent_id, version_number)

    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    published = await manager.publish_version(agent_id, version.id, UUID(user_id))

    return {
        "id": str(published.id),
        "version_number": published.version_number,
        "status": published.status.value,
        "published_at": published.published_at.isoformat() if published.published_at else None,
    }


@router.post("/{agent_id}/rollback")
async def rollback_agent(
    agent_id: UUID,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    target_version: int = Query(..., description="Version to rollback to"),
    user_id: str = Query(..., description="User ID"),
):
    """Rollback an agent to a previous version."""
    from aswa_agents.governance import VersionManager

    manager = VersionManager(UUID(tenant_id))

    try:
        version = await manager.rollback(agent_id, target_version, UUID(user_id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "id": str(version.id),
        "version_number": version.version_number,
        "status": version.status.value,
        "changelog": version.changelog,
    }


@router.get("/{agent_id}/audit")
async def get_agent_audit_log(
    agent_id: UUID,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Get audit log for an agent."""
    from aswa_agents.governance import AuditLogger

    logger = AuditLogger(UUID(tenant_id))
    entries = await logger.query(
        resource_id=agent_id,
        limit=limit,
        offset=offset,
    )

    return {
        "entries": [
            {
                "id": str(e.id),
                "action": e.action.value,
                "actor_id": str(e.actor_id),
                "details": e.details,
                "timestamp": e.timestamp.isoformat(),
            }
            for e in entries
        ]
    }
