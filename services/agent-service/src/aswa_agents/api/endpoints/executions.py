"""Execution management endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from aswa_agents.api.dependencies import get_current_tenant, get_db_session
from aswa_agents.api.schemas import ExecutionResponse, TriggerRequest
from aswa_agents.core.orchestrator import AgentOrchestrator
from aswa_agents.core.models import TriggerData
from aswa_agents.core.types import TriggerType
from aswa_agents.persistence.repository import ActionRepository, ExecutionRepository
from aswa_agents.approval.service import ApprovalService


router = APIRouter()

# In-memory instances for now (production would use DI)
_action_repository = ActionRepository()
_execution_repository = ExecutionRepository()
_approval_service = ApprovalService()


def get_orchestrator() -> AgentOrchestrator:
    """Get orchestrator instance."""
    return AgentOrchestrator(
        action_repository=_action_repository,
        execution_repository=_execution_repository,
        approval_service=_approval_service,
    )


@router.post("/trigger", response_model=dict)
async def trigger_agents(
    request: TriggerRequest,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    trigger_type: str = Query(default="manual"),
    orchestrator: AgentOrchestrator = Depends(get_orchestrator),
) -> dict:
    """Trigger agents with custom input data."""
    trigger = TriggerData(
        trigger_type=TriggerType(trigger_type),
        payload=request.input_data,
    )
    trigger.payload["tenant_id"] = tenant_id

    execution_ids = await orchestrator.process_trigger(
        trigger=trigger,
        tenant_config={"tenant_id": tenant_id},
        dry_run=request.dry_run,
    )

    return {
        "execution_ids": [str(eid) for eid in execution_ids],
        "dry_run": request.dry_run,
    }


@router.get("/{execution_id}")
async def get_execution(
    execution_id: UUID,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
) -> dict:
    """Get execution details."""
    execution = await _execution_repository.get(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    if execution.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return {
        "execution_id": str(execution.execution_id),
        "agent_id": str(execution.agent_id) if execution.agent_id else None,
        "tenant_id": execution.tenant_id,
        "status": execution.status.value,
        "started_at": execution.started_at.isoformat() if execution.started_at else None,
        "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
        "dry_run": execution.dry_run,
        "action_count": len(execution.action_results),
    }


@router.get("")
async def list_executions(
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    agent_name: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict:
    """List executions for tenant."""
    executions, total = await _execution_repository.list_by_tenant(
        tenant_id=tenant_id,
        agent_name=agent_name,
        status=status,
        limit=limit,
        offset=offset,
    )

    return {
        "executions": [
            {
                "execution_id": str(e.execution_id),
                "status": e.status.value,
                "started_at": e.started_at.isoformat() if e.started_at else None,
                "completed_at": e.completed_at.isoformat() if e.completed_at else None,
            }
            for e in executions
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/{execution_id}/cancel")
async def cancel_execution(
    execution_id: UUID,
    tenant_id: Annotated[str, Depends(get_current_tenant)],
    orchestrator: AgentOrchestrator = Depends(get_orchestrator),
) -> dict:
    """Cancel a pending or running execution."""
    # Verify execution belongs to tenant
    execution = await _execution_repository.get(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    if execution.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")

    cancelled = await orchestrator.cancel_execution(execution_id)
    if not cancelled:
        raise HTTPException(status_code=400, detail="Cannot cancel execution")
    return {"cancelled": True}
