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
    # Implementation in Task 9.5.1
    raise HTTPException(status_code=501, detail="Not implemented")
