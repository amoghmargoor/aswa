# Task 9.8.4: Agent API

## Objective

Implement a comprehensive REST API for the agent platform that provides endpoints for agent management, execution, monitoring, and integration with external systems.

## Prerequisites

- Task 9.8.1-9.8.3 completed (Triggers, OAuth, Webhooks)
- Agent core infrastructure (9.1.x)
- Action blocks system (9.4.x)
- Authentication/authorization infrastructure

## Implementation

### Step 1: API Router Structure

```python
# services/agent-service/src/aswa_agents/api/__init__.py
"""API router configuration."""

from fastapi import APIRouter

from aswa_agents.api.agents import router as agents_router
from aswa_agents.api.executions import router as executions_router
from aswa_agents.api.actions import router as actions_router
from aswa_agents.api.templates import router as templates_router
from aswa_agents.api.triggers import router as triggers_router
from aswa_agents.api.webhooks import router as webhooks_router
from aswa_agents.api.oauth import router as oauth_router
from aswa_agents.api.health import router as health_router

api_router = APIRouter(prefix="/api/v1")

# Register all routers
api_router.include_router(agents_router)
api_router.include_router(executions_router)
api_router.include_router(actions_router)
api_router.include_router(templates_router)
api_router.include_router(triggers_router)
api_router.include_router(webhooks_router)
api_router.include_router(oauth_router)
api_router.include_router(health_router)
```

### Step 2: Agent API Endpoints

```python
# services/agent-service/src/aswa_agents/api/agents.py
"""API endpoints for agent management."""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Depends, BackgroundTasks
from pydantic import BaseModel, Field

from aswa_agents.services.agent_service import AgentService
from aswa_agents.services.execution_service import ExecutionService
from aswa_agents.models.agent import AgentStatus, AgentType
from aswa_agents.api.auth import get_current_user, get_tenant_id
from aswa_agents.api.pagination import PaginatedResponse, PaginationParams

router = APIRouter(prefix="/agents", tags=["agents"])


class AgentCreate(BaseModel):
    """Request to create an agent."""

    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    type: AgentType = AgentType.CONVERSATIONAL
    system_prompt: str | None = None
    configuration: dict[str, Any] = Field(default_factory=dict)
    actions: list[UUID] = Field(default_factory=list)
    triggers: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentUpdate(BaseModel):
    """Request to update an agent."""

    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    configuration: dict[str, Any] | None = None
    actions: list[UUID] | None = None
    triggers: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] | None = None
    status: AgentStatus | None = None


class AgentResponse(BaseModel):
    """Agent response model."""

    id: UUID
    name: str
    description: str | None
    type: str
    status: str
    version: int
    system_prompt: str | None
    configuration: dict[str, Any]
    actions: list[dict[str, Any]]
    triggers: list[dict[str, Any]]
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    created_by: str | None
    execution_count: int
    last_execution_at: datetime | None


class AgentExecuteRequest(BaseModel):
    """Request to execute an agent."""

    input: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    async_execution: bool = False
    timeout_seconds: int = Field(default=300, ge=1, le=3600)
    callback_url: str | None = None


class AgentExecuteResponse(BaseModel):
    """Response from agent execution."""

    execution_id: UUID
    status: str
    result: dict[str, Any] | None = None
    error: str | None = None
    started_at: datetime
    completed_at: datetime | None = None


@router.post("", response_model=AgentResponse)
async def create_agent(
    agent: AgentCreate,
    user_id: str = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
) -> AgentResponse:
    """Create a new agent."""
    service = AgentService()

    try:
        result = await service.create_agent(
            tenant_id=tenant_id,
            name=agent.name,
            description=agent.description,
            agent_type=agent.type,
            system_prompt=agent.system_prompt,
            configuration=agent.configuration,
            actions=agent.actions,
            triggers=agent.triggers,
            metadata=agent.metadata,
            created_by=user_id,
        )

        return AgentResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=PaginatedResponse[AgentResponse])
async def list_agents(
    pagination: PaginationParams = Depends(),
    status: AgentStatus | None = None,
    type: AgentType | None = None,
    search: str | None = None,
    tenant_id: str = Depends(get_tenant_id),
) -> PaginatedResponse[AgentResponse]:
    """List agents with filtering and pagination."""
    service = AgentService()

    agents, total = await service.list_agents(
        tenant_id=tenant_id,
        status=status,
        agent_type=type,
        search=search,
        offset=pagination.offset,
        limit=pagination.limit,
    )

    return PaginatedResponse(
        items=[AgentResponse(**a) for a in agents],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: UUID,
    tenant_id: str = Depends(get_tenant_id),
) -> AgentResponse:
    """Get agent by ID."""
    service = AgentService()

    agent = await service.get_agent(agent_id, tenant_id)

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return AgentResponse(**agent)


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: UUID,
    update: AgentUpdate,
    tenant_id: str = Depends(get_tenant_id),
) -> AgentResponse:
    """Update an agent."""
    service = AgentService()

    updates = update.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    agent = await service.update_agent(agent_id, tenant_id, updates)

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return AgentResponse(**agent)


@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: UUID,
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, Any]:
    """Delete an agent."""
    service = AgentService()

    success = await service.delete_agent(agent_id, tenant_id)

    if not success:
        raise HTTPException(status_code=404, detail="Agent not found")

    return {"deleted": True}


@router.post("/{agent_id}/execute", response_model=AgentExecuteResponse)
async def execute_agent(
    agent_id: UUID,
    request: AgentExecuteRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
) -> AgentExecuteResponse:
    """Execute an agent."""
    agent_service = AgentService()
    execution_service = ExecutionService()

    # Verify agent exists
    agent = await agent_service.get_agent(agent_id, tenant_id)

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if agent["status"] != AgentStatus.ACTIVE.value:
        raise HTTPException(status_code=400, detail="Agent is not active")

    # Create execution
    execution = await execution_service.create_execution(
        tenant_id=tenant_id,
        agent_id=agent_id,
        input_data=request.input,
        context=request.context,
        triggered_by=user_id,
        timeout_seconds=request.timeout_seconds,
        callback_url=request.callback_url,
    )

    if request.async_execution:
        # Run in background
        background_tasks.add_task(
            execution_service.run_execution,
            execution["id"],
        )

        return AgentExecuteResponse(
            execution_id=execution["id"],
            status="pending",
            started_at=execution["created_at"],
        )
    else:
        # Run synchronously
        result = await execution_service.run_execution(execution["id"])

        return AgentExecuteResponse(
            execution_id=execution["id"],
            status=result["status"],
            result=result.get("result"),
            error=result.get("error"),
            started_at=result["started_at"],
            completed_at=result.get("completed_at"),
        )


@router.post("/{agent_id}/deploy")
async def deploy_agent(
    agent_id: UUID,
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, Any]:
    """Deploy an agent (activate it)."""
    service = AgentService()

    result = await service.deploy_agent(agent_id, tenant_id)

    if not result:
        raise HTTPException(status_code=404, detail="Agent not found")

    return result


@router.post("/{agent_id}/undeploy")
async def undeploy_agent(
    agent_id: UUID,
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, Any]:
    """Undeploy an agent (deactivate it)."""
    service = AgentService()

    result = await service.undeploy_agent(agent_id, tenant_id)

    if not result:
        raise HTTPException(status_code=404, detail="Agent not found")

    return result


@router.post("/{agent_id}/clone", response_model=AgentResponse)
async def clone_agent(
    agent_id: UUID,
    name: str = Query(..., description="Name for the cloned agent"),
    user_id: str = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
) -> AgentResponse:
    """Clone an existing agent."""
    service = AgentService()

    cloned = await service.clone_agent(
        agent_id=agent_id,
        tenant_id=tenant_id,
        new_name=name,
        created_by=user_id,
    )

    if not cloned:
        raise HTTPException(status_code=404, detail="Agent not found")

    return AgentResponse(**cloned)


@router.get("/{agent_id}/versions")
async def list_agent_versions(
    agent_id: UUID,
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, Any]:
    """List agent version history."""
    service = AgentService()

    versions = await service.list_versions(agent_id, tenant_id)

    return {"versions": versions}


@router.post("/{agent_id}/versions/{version}/restore")
async def restore_agent_version(
    agent_id: UUID,
    version: int,
    tenant_id: str = Depends(get_tenant_id),
) -> AgentResponse:
    """Restore agent to a previous version."""
    service = AgentService()

    agent = await service.restore_version(agent_id, tenant_id, version)

    if not agent:
        raise HTTPException(status_code=404, detail="Version not found")

    return AgentResponse(**agent)


@router.get("/{agent_id}/stats")
async def get_agent_stats(
    agent_id: UUID,
    days: int = Query(30, ge=1, le=365),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, Any]:
    """Get agent execution statistics."""
    service = AgentService()

    stats = await service.get_agent_stats(agent_id, tenant_id, days)

    if not stats:
        raise HTTPException(status_code=404, detail="Agent not found")

    return stats
```

### Step 3: Execution API Endpoints

```python
# services/agent-service/src/aswa_agents/api/executions.py
"""API endpoints for execution management."""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from aswa_agents.services.execution_service import ExecutionService
from aswa_agents.models.execution import ExecutionStatus
from aswa_agents.api.auth import get_current_user, get_tenant_id
from aswa_agents.api.pagination import PaginatedResponse, PaginationParams

router = APIRouter(prefix="/executions", tags=["executions"])


class ExecutionResponse(BaseModel):
    """Execution response model."""

    id: UUID
    agent_id: UUID
    status: str
    input_data: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None
    steps: list[dict[str, Any]]
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int | None
    triggered_by: str | None
    trigger_type: str | None
    created_at: datetime


class ExecutionStepResponse(BaseModel):
    """Execution step response model."""

    id: UUID
    execution_id: UUID
    step_number: int
    action_id: UUID | None
    action_type: str
    status: str
    input_data: dict[str, Any]
    output_data: dict[str, Any] | None
    error: str | None
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int | None


@router.get("", response_model=PaginatedResponse[ExecutionResponse])
async def list_executions(
    pagination: PaginationParams = Depends(),
    agent_id: UUID | None = None,
    status: ExecutionStatus | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    tenant_id: str = Depends(get_tenant_id),
) -> PaginatedResponse[ExecutionResponse]:
    """List executions with filtering."""
    service = ExecutionService()

    executions, total = await service.list_executions(
        tenant_id=tenant_id,
        agent_id=agent_id,
        status=status,
        from_date=from_date,
        to_date=to_date,
        offset=pagination.offset,
        limit=pagination.limit,
    )

    return PaginatedResponse(
        items=[ExecutionResponse(**e) for e in executions],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.get("/{execution_id}", response_model=ExecutionResponse)
async def get_execution(
    execution_id: UUID,
    tenant_id: str = Depends(get_tenant_id),
) -> ExecutionResponse:
    """Get execution by ID."""
    service = ExecutionService()

    execution = await service.get_execution(execution_id, tenant_id)

    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    return ExecutionResponse(**execution)


@router.get("/{execution_id}/steps")
async def get_execution_steps(
    execution_id: UUID,
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, Any]:
    """Get execution steps."""
    service = ExecutionService()

    execution = await service.get_execution(execution_id, tenant_id)

    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    return {"steps": execution.get("steps", [])}


@router.post("/{execution_id}/cancel")
async def cancel_execution(
    execution_id: UUID,
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, Any]:
    """Cancel a running execution."""
    service = ExecutionService()

    success = await service.cancel_execution(execution_id, tenant_id)

    if not success:
        raise HTTPException(status_code=400, detail="Cannot cancel execution")

    return {"cancelled": True}


@router.post("/{execution_id}/retry", response_model=ExecutionResponse)
async def retry_execution(
    execution_id: UUID,
    tenant_id: str = Depends(get_tenant_id),
    user_id: str = Depends(get_current_user),
) -> ExecutionResponse:
    """Retry a failed execution."""
    service = ExecutionService()

    new_execution = await service.retry_execution(
        execution_id=execution_id,
        tenant_id=tenant_id,
        triggered_by=user_id,
    )

    if not new_execution:
        raise HTTPException(status_code=400, detail="Cannot retry execution")

    return ExecutionResponse(**new_execution)


@router.get("/{execution_id}/logs")
async def get_execution_logs(
    execution_id: UUID,
    level: str | None = Query(None, description="Filter by log level"),
    limit: int = Query(100, ge=1, le=1000),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, Any]:
    """Get execution logs."""
    service = ExecutionService()

    logs = await service.get_execution_logs(
        execution_id=execution_id,
        tenant_id=tenant_id,
        level=level,
        limit=limit,
    )

    return {"logs": logs}


@router.websocket("/{execution_id}/stream")
async def stream_execution(
    websocket: WebSocket,
    execution_id: UUID,
):
    """Stream execution updates via WebSocket."""
    await websocket.accept()

    service = ExecutionService()

    try:
        async for update in service.stream_execution(execution_id):
            await websocket.send_json(update)

            if update.get("status") in ["completed", "failed", "cancelled"]:
                break

    except WebSocketDisconnect:
        pass
    finally:
        await websocket.close()
```

### Step 4: Action API Endpoints

```python
# services/agent-service/src/aswa_agents/api/actions.py
"""API endpoints for action management."""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from aswa_agents.services.action_service import ActionService
from aswa_agents.models.action import ActionType, ActionCategory
from aswa_agents.api.auth import get_current_user, get_tenant_id
from aswa_agents.api.pagination import PaginatedResponse, PaginationParams

router = APIRouter(prefix="/actions", tags=["actions"])


class ActionCreate(BaseModel):
    """Request to create an action."""

    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    type: ActionType
    category: ActionCategory = ActionCategory.GENERAL
    configuration: dict[str, Any] = Field(default_factory=dict)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    requires_approval: bool = False
    timeout_seconds: int = 60
    retry_config: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ActionUpdate(BaseModel):
    """Request to update an action."""

    name: str | None = None
    description: str | None = None
    configuration: dict[str, Any] | None = None
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    requires_approval: bool | None = None
    timeout_seconds: int | None = None
    metadata: dict[str, Any] | None = None


class ActionResponse(BaseModel):
    """Action response model."""

    id: UUID
    name: str
    description: str | None
    type: str
    category: str
    configuration: dict[str, Any]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    requires_approval: bool
    timeout_seconds: int
    enabled: bool
    created_at: datetime
    updated_at: datetime


class ActionTestRequest(BaseModel):
    """Request to test an action."""

    input_data: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = False


class ActionTestResponse(BaseModel):
    """Response from action test."""

    success: bool
    output: dict[str, Any] | None = None
    error: str | None = None
    duration_ms: int


@router.post("", response_model=ActionResponse)
async def create_action(
    action: ActionCreate,
    user_id: str = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
) -> ActionResponse:
    """Create a new action."""
    service = ActionService()

    try:
        result = await service.create_action(
            tenant_id=tenant_id,
            name=action.name,
            description=action.description,
            action_type=action.type,
            category=action.category,
            configuration=action.configuration,
            input_schema=action.input_schema,
            output_schema=action.output_schema,
            requires_approval=action.requires_approval,
            timeout_seconds=action.timeout_seconds,
            retry_config=action.retry_config,
            metadata=action.metadata,
            created_by=user_id,
        )

        return ActionResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=PaginatedResponse[ActionResponse])
async def list_actions(
    pagination: PaginationParams = Depends(),
    type: ActionType | None = None,
    category: ActionCategory | None = None,
    search: str | None = None,
    tenant_id: str = Depends(get_tenant_id),
) -> PaginatedResponse[ActionResponse]:
    """List actions with filtering."""
    service = ActionService()

    actions, total = await service.list_actions(
        tenant_id=tenant_id,
        action_type=type,
        category=category,
        search=search,
        offset=pagination.offset,
        limit=pagination.limit,
    )

    return PaginatedResponse(
        items=[ActionResponse(**a) for a in actions],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.get("/builtin")
async def list_builtin_actions() -> dict[str, Any]:
    """List all built-in actions."""
    service = ActionService()

    actions = await service.list_builtin_actions()

    return {"actions": actions}


@router.get("/categories")
async def list_categories() -> dict[str, Any]:
    """List all action categories."""
    return {
        "categories": [
            {"value": c.value, "name": c.name}
            for c in ActionCategory
        ]
    }


@router.get("/{action_id}", response_model=ActionResponse)
async def get_action(
    action_id: UUID,
    tenant_id: str = Depends(get_tenant_id),
) -> ActionResponse:
    """Get action by ID."""
    service = ActionService()

    action = await service.get_action(action_id, tenant_id)

    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    return ActionResponse(**action)


@router.put("/{action_id}", response_model=ActionResponse)
async def update_action(
    action_id: UUID,
    update: ActionUpdate,
    tenant_id: str = Depends(get_tenant_id),
) -> ActionResponse:
    """Update an action."""
    service = ActionService()

    updates = update.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    action = await service.update_action(action_id, tenant_id, updates)

    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    return ActionResponse(**action)


@router.delete("/{action_id}")
async def delete_action(
    action_id: UUID,
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, Any]:
    """Delete an action."""
    service = ActionService()

    success = await service.delete_action(action_id, tenant_id)

    if not success:
        raise HTTPException(status_code=404, detail="Action not found")

    return {"deleted": True}


@router.post("/{action_id}/test", response_model=ActionTestResponse)
async def test_action(
    action_id: UUID,
    request: ActionTestRequest,
    tenant_id: str = Depends(get_tenant_id),
) -> ActionTestResponse:
    """Test an action with sample input."""
    service = ActionService()

    result = await service.test_action(
        action_id=action_id,
        tenant_id=tenant_id,
        input_data=request.input_data,
        dry_run=request.dry_run,
    )

    return ActionTestResponse(**result)


@router.get("/{action_id}/usage")
async def get_action_usage(
    action_id: UUID,
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, Any]:
    """Get action usage information."""
    service = ActionService()

    usage = await service.get_action_usage(action_id, tenant_id)

    if not usage:
        raise HTTPException(status_code=404, detail="Action not found")

    return usage
```

### Step 5: Trigger API Endpoints

```python
# services/agent-service/src/aswa_agents/api/triggers.py
"""API endpoints for trigger management."""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from aswa_agents.connectors.registry import get_connector_registry
from aswa_agents.connectors.base import TriggerType
from aswa_agents.api.auth import get_current_user, get_tenant_id

router = APIRouter(prefix="/triggers", tags=["triggers"])


class WebhookEndpointCreate(BaseModel):
    """Request to create a webhook endpoint."""

    agent_id: UUID
    description: str | None = None


class WebhookEndpointResponse(BaseModel):
    """Webhook endpoint response."""

    id: str
    agent_id: str
    path: str
    secret: str
    url: str
    description: str | None
    enabled: bool
    created_at: datetime


class ScheduleCreate(BaseModel):
    """Request to create a scheduled trigger."""

    agent_id: UUID
    name: str
    description: str | None = None
    cron_expression: str | None = None
    interval_seconds: int | None = None
    run_at: datetime | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class ScheduleResponse(BaseModel):
    """Schedule response."""

    id: str
    agent_id: str
    name: str
    description: str | None
    cron_expression: str | None
    interval_seconds: int | None
    run_at: datetime | None
    next_run: datetime | None
    last_run: datetime | None
    run_count: int
    enabled: bool
    created_at: datetime


@router.get("/types")
async def list_trigger_types() -> dict[str, Any]:
    """List available trigger types."""
    return {
        "types": [
            {"value": t.value, "name": t.name}
            for t in TriggerType
        ]
    }


@router.get("/status")
async def get_trigger_status() -> dict[str, Any]:
    """Get status of all trigger connectors."""
    registry = get_connector_registry()

    return await registry.health_check_all()


# Webhook endpoints

@router.post("/webhooks", response_model=WebhookEndpointResponse)
async def create_webhook_endpoint(
    request: WebhookEndpointCreate,
    tenant_id: str = Depends(get_tenant_id),
) -> WebhookEndpointResponse:
    """Create a webhook endpoint for an agent."""
    import secrets
    from uuid import uuid4

    registry = get_connector_registry()
    webhook_connector = registry.get("webhook")

    if not webhook_connector:
        raise HTTPException(status_code=503, detail="Webhook connector not available")

    endpoint_id = str(uuid4())
    secret = secrets.token_urlsafe(32)

    endpoint = await webhook_connector.register_endpoint(
        tenant_id=tenant_id,
        endpoint_id=endpoint_id,
        secret=secret,
        agent_id=str(request.agent_id),
        description=request.description,
    )

    return WebhookEndpointResponse(
        id=endpoint.id,
        agent_id=endpoint.agent_id,
        path=endpoint.path,
        secret=endpoint.secret,
        url=f"/api/v1/webhooks/{endpoint.id}",
        description=endpoint.description,
        enabled=endpoint.enabled,
        created_at=endpoint.created_at,
    )


@router.get("/webhooks")
async def list_webhook_endpoints(
    agent_id: UUID | None = None,
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, Any]:
    """List webhook endpoints."""
    registry = get_connector_registry()
    webhook_connector = registry.get("webhook")

    if not webhook_connector:
        return {"endpoints": []}

    endpoints = [
        e for e in webhook_connector._endpoints.values()
        if e.tenant_id == tenant_id
        and (agent_id is None or e.agent_id == str(agent_id))
    ]

    return {
        "endpoints": [
            {
                "id": e.id,
                "agent_id": e.agent_id,
                "path": e.path,
                "enabled": e.enabled,
                "created_at": e.created_at.isoformat(),
            }
            for e in endpoints
        ]
    }


@router.delete("/webhooks/{endpoint_id}")
async def delete_webhook_endpoint(
    endpoint_id: str,
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, Any]:
    """Delete a webhook endpoint."""
    registry = get_connector_registry()
    webhook_connector = registry.get("webhook")

    if not webhook_connector:
        raise HTTPException(status_code=503, detail="Webhook connector not available")

    # Verify ownership
    endpoint = webhook_connector._endpoints.get(endpoint_id)
    if not endpoint or endpoint.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    await webhook_connector.remove_endpoint(endpoint_id)

    return {"deleted": True}


# Schedule endpoints

@router.post("/schedules", response_model=ScheduleResponse)
async def create_schedule(
    request: ScheduleCreate,
    tenant_id: str = Depends(get_tenant_id),
) -> ScheduleResponse:
    """Create a scheduled trigger for an agent."""
    registry = get_connector_registry()
    schedule_connector = registry.get("schedule")

    if not schedule_connector:
        raise HTTPException(status_code=503, detail="Schedule connector not available")

    try:
        task = await schedule_connector.register_task(
            tenant_id=tenant_id,
            agent_id=str(request.agent_id),
            name=request.name,
            description=request.description,
            cron_expression=request.cron_expression,
            interval_seconds=request.interval_seconds,
            run_at=request.run_at,
            payload=request.payload,
        )

        return ScheduleResponse(
            id=task.id,
            agent_id=task.agent_id,
            name=task.name,
            description=task.description,
            cron_expression=task.cron_expression,
            interval_seconds=task.interval_seconds,
            run_at=task.run_at,
            next_run=task.next_run,
            last_run=task.last_run,
            run_count=task.run_count,
            enabled=task.enabled,
            created_at=task.created_at,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/schedules")
async def list_schedules(
    agent_id: UUID | None = None,
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, Any]:
    """List scheduled triggers."""
    registry = get_connector_registry()
    schedule_connector = registry.get("schedule")

    if not schedule_connector:
        return {"schedules": []}

    tasks = await schedule_connector.list_tasks(
        tenant_id=tenant_id,
        agent_id=str(agent_id) if agent_id else None,
    )

    return {
        "schedules": [
            {
                "id": t.id,
                "agent_id": t.agent_id,
                "name": t.name,
                "cron_expression": t.cron_expression,
                "interval_seconds": t.interval_seconds,
                "next_run": t.next_run.isoformat() if t.next_run else None,
                "last_run": t.last_run.isoformat() if t.last_run else None,
                "run_count": t.run_count,
                "enabled": t.enabled,
            }
            for t in tasks
        ]
    }


@router.get("/schedules/{schedule_id}")
async def get_schedule(
    schedule_id: str,
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, Any]:
    """Get a scheduled trigger."""
    registry = get_connector_registry()
    schedule_connector = registry.get("schedule")

    if not schedule_connector:
        raise HTTPException(status_code=503, detail="Schedule connector not available")

    task = await schedule_connector.get_task(schedule_id)

    if not task or task.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Schedule not found")

    return {
        "id": task.id,
        "agent_id": task.agent_id,
        "name": task.name,
        "description": task.description,
        "cron_expression": task.cron_expression,
        "interval_seconds": task.interval_seconds,
        "run_at": task.run_at.isoformat() if task.run_at else None,
        "next_run": task.next_run.isoformat() if task.next_run else None,
        "last_run": task.last_run.isoformat() if task.last_run else None,
        "run_count": task.run_count,
        "enabled": task.enabled,
        "payload": task.payload,
    }


@router.put("/schedules/{schedule_id}")
async def update_schedule(
    schedule_id: str,
    updates: dict[str, Any],
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, Any]:
    """Update a scheduled trigger."""
    registry = get_connector_registry()
    schedule_connector = registry.get("schedule")

    if not schedule_connector:
        raise HTTPException(status_code=503, detail="Schedule connector not available")

    # Verify ownership
    task = await schedule_connector.get_task(schedule_id)
    if not task or task.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Schedule not found")

    updated = await schedule_connector.update_task(schedule_id, updates)

    return {
        "id": updated.id,
        "name": updated.name,
        "next_run": updated.next_run.isoformat() if updated.next_run else None,
        "enabled": updated.enabled,
    }


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: str,
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, Any]:
    """Delete a scheduled trigger."""
    registry = get_connector_registry()
    schedule_connector = registry.get("schedule")

    if not schedule_connector:
        raise HTTPException(status_code=503, detail="Schedule connector not available")

    # Verify ownership
    task = await schedule_connector.get_task(schedule_id)
    if not task or task.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Schedule not found")

    await schedule_connector.remove_task(schedule_id)

    return {"deleted": True}
```

### Step 6: Health and Status API

```python
# services/agent-service/src/aswa_agents/api/health.py
"""Health check and status endpoints."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter
import structlog

from aswa_agents.connectors.registry import get_connector_registry
from aswa_agents.db.session import check_db_connection
from aswa_agents.services.cache_service import CacheService

router = APIRouter(prefix="/health", tags=["health"])
logger = structlog.get_logger()


@router.get("")
async def health_check() -> dict[str, Any]:
    """Basic health check."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "agent-service",
    }


@router.get("/ready")
async def readiness_check() -> dict[str, Any]:
    """Readiness check for Kubernetes."""
    checks = {}
    overall_healthy = True

    # Check database
    try:
        db_healthy = await check_db_connection()
        checks["database"] = {"status": "healthy" if db_healthy else "unhealthy"}
        if not db_healthy:
            overall_healthy = False
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False

    # Check cache
    try:
        cache = CacheService()
        cache_healthy = await cache.ping()
        checks["cache"] = {"status": "healthy" if cache_healthy else "unhealthy"}
        if not cache_healthy:
            overall_healthy = False
    except Exception as e:
        checks["cache"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False

    return {
        "status": "ready" if overall_healthy else "not_ready",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks,
    }


@router.get("/live")
async def liveness_check() -> dict[str, Any]:
    """Liveness check for Kubernetes."""
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/detailed")
async def detailed_health() -> dict[str, Any]:
    """Detailed health status."""
    checks = {}

    # Database check
    try:
        db_healthy = await check_db_connection()
        checks["database"] = {
            "status": "healthy" if db_healthy else "unhealthy",
            "type": "postgresql",
        }
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "error": str(e)}

    # Cache check
    try:
        cache = CacheService()
        cache_healthy = await cache.ping()
        cache_info = await cache.info() if cache_healthy else {}
        checks["cache"] = {
            "status": "healthy" if cache_healthy else "unhealthy",
            "type": "redis",
            "info": cache_info,
        }
    except Exception as e:
        checks["cache"] = {"status": "unhealthy", "error": str(e)}

    # Connector status
    try:
        registry = get_connector_registry()
        connector_health = await registry.health_check_all()
        checks["connectors"] = connector_health
    except Exception as e:
        checks["connectors"] = {"status": "error", "error": str(e)}

    # Calculate overall status
    unhealthy = any(
        c.get("status") in ["unhealthy", "error"]
        for c in checks.values()
        if isinstance(c, dict)
    )

    return {
        "status": "unhealthy" if unhealthy else "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "agent-service",
        "version": "1.0.0",
        "checks": checks,
    }


@router.get("/metrics")
async def get_metrics() -> dict[str, Any]:
    """Get service metrics."""
    from aswa_agents.services.metrics_service import MetricsService

    metrics = MetricsService()

    return await metrics.get_all_metrics()
```

### Step 7: Authentication Dependencies

```python
# services/agent-service/src/aswa_agents/api/auth.py
"""Authentication dependencies for API endpoints."""

from typing import Any

from fastapi import Depends, HTTPException, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import structlog

logger = structlog.get_logger()
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    x_user_id: str | None = Header(None, alias="X-User-ID"),
) -> str:
    """
    Get the current user from the request.

    Supports both JWT tokens and direct user ID headers (for internal calls).
    """
    if x_user_id:
        return x_user_id

    if credentials:
        try:
            # Validate JWT token
            from aswa_agents.services.auth_service import AuthService

            auth = AuthService()
            user = await auth.validate_token(credentials.credentials)

            if user:
                return user["user_id"]

        except Exception as e:
            logger.warning("Token validation failed", error=str(e))

    raise HTTPException(
        status_code=401,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_tenant_id(
    x_tenant_id: str | None = Header(None, alias="X-Tenant-ID"),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    """
    Get the tenant ID from the request.

    Supports both direct header and extraction from JWT token.
    """
    if x_tenant_id:
        return x_tenant_id

    if credentials:
        try:
            from aswa_agents.services.auth_service import AuthService

            auth = AuthService()
            user = await auth.validate_token(credentials.credentials)

            if user and "tenant_id" in user:
                return user["tenant_id"]

        except Exception:
            pass

    # Default tenant for development
    return "default-tenant"


async def require_admin(
    user_id: str = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, Any]:
    """Require admin role."""
    from aswa_agents.services.auth_service import AuthService

    auth = AuthService()
    is_admin = await auth.check_role(user_id, tenant_id, "admin")

    if not is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    return {"user_id": user_id, "tenant_id": tenant_id, "role": "admin"}


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    x_user_id: str | None = Header(None, alias="X-User-ID"),
) -> str | None:
    """Get current user if authenticated, None otherwise."""
    try:
        return await get_current_user(credentials, x_user_id)
    except HTTPException:
        return None
```

### Step 8: Pagination Utilities

```python
# services/agent-service/src/aswa_agents/api/pagination.py
"""Pagination utilities for API endpoints."""

from typing import Generic, TypeVar
from fastapi import Query
from pydantic import BaseModel

T = TypeVar("T")


class PaginationParams:
    """Pagination query parameters."""

    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number"),
        page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    ):
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        """Calculate offset from page number."""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Get limit (same as page_size)."""
        return self.page_size


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper."""

    items: list[T]
    total: int
    offset: int
    limit: int

    @property
    def page(self) -> int:
        """Current page number."""
        return (self.offset // self.limit) + 1 if self.limit > 0 else 1

    @property
    def pages(self) -> int:
        """Total number of pages."""
        return (self.total + self.limit - 1) // self.limit if self.limit > 0 else 1

    @property
    def has_next(self) -> bool:
        """Whether there is a next page."""
        return self.offset + self.limit < self.total

    @property
    def has_prev(self) -> bool:
        """Whether there is a previous page."""
        return self.offset > 0

    model_config = {
        "json_schema_extra": {
            "example": {
                "items": [],
                "total": 100,
                "offset": 0,
                "limit": 20,
            }
        }
    }
```

### Step 9: FastAPI Application Setup

```python
# services/agent-service/src/aswa_agents/main.py
"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog

from aswa_agents.api import api_router
from aswa_agents.connectors.registry import get_connector_registry
from aswa_agents.webhooks.service import WebhookService
from aswa_agents.config import settings

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    logger.info("Starting agent service")

    # Start connectors
    registry = get_connector_registry()
    await registry.start_all()

    # Start webhook service
    webhook_service = WebhookService()
    await webhook_service.start()

    yield

    # Shutdown
    logger.info("Shutting down agent service")

    await webhook_service.stop()
    await registry.stop_all()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="ASWA Agent Service",
        description="AI Agent Platform API",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.DOCS_ENABLED else None,
        redoc_url="/redoc" if settings.DOCS_ENABLED else None,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API router
    app.include_router(api_router)

    # Include webhook receiver router
    registry = get_connector_registry()
    webhook_connector = registry.get("webhook")
    if webhook_connector:
        app.include_router(webhook_connector.router)

    # Exception handlers
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc)},
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error("Unhandled exception", error=str(exc), path=request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "aswa_agents.main:app",
        host="0.0.0.0",
        port=8080,
        reload=settings.DEBUG,
    )
```

## Test Cases

```python
# services/agent-service/tests/unit/test_agent_api.py
"""Tests for agent API endpoints."""

import pytest
from datetime import datetime
from uuid import uuid4
from unittest.mock import AsyncMock, patch, MagicMock

from fastapi.testclient import TestClient
from httpx import AsyncClient

from aswa_agents.main import app
from aswa_agents.models.agent import AgentStatus, AgentType


class TestAgentEndpoints:
    """Test agent API endpoints."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        return {
            "X-User-ID": "test-user",
            "X-Tenant-ID": "test-tenant",
        }

    def test_create_agent(self, client, auth_headers):
        """Test creating an agent."""
        with patch("aswa_agents.api.agents.AgentService") as mock_service:
            mock_instance = MagicMock()
            mock_instance.create_agent = AsyncMock(return_value={
                "id": str(uuid4()),
                "name": "Test Agent",
                "description": "Test description",
                "type": AgentType.CONVERSATIONAL.value,
                "status": AgentStatus.DRAFT.value,
                "version": 1,
                "system_prompt": None,
                "configuration": {},
                "actions": [],
                "triggers": [],
                "metadata": {},
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "created_by": "test-user",
                "execution_count": 0,
                "last_execution_at": None,
            })
            mock_service.return_value = mock_instance

            response = client.post(
                "/api/v1/agents",
                json={
                    "name": "Test Agent",
                    "description": "Test description",
                    "type": "conversational",
                },
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "Test Agent"

    def test_list_agents(self, client, auth_headers):
        """Test listing agents."""
        with patch("aswa_agents.api.agents.AgentService") as mock_service:
            mock_instance = MagicMock()
            mock_instance.list_agents = AsyncMock(return_value=(
                [{
                    "id": str(uuid4()),
                    "name": "Agent 1",
                    "description": None,
                    "type": "conversational",
                    "status": "active",
                    "version": 1,
                    "system_prompt": None,
                    "configuration": {},
                    "actions": [],
                    "triggers": [],
                    "metadata": {},
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                    "created_by": "test-user",
                    "execution_count": 10,
                    "last_execution_at": datetime.utcnow(),
                }],
                1,
            ))
            mock_service.return_value = mock_instance

            response = client.get(
                "/api/v1/agents",
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 1
            assert data["total"] == 1

    def test_get_agent(self, client, auth_headers):
        """Test getting an agent by ID."""
        agent_id = uuid4()

        with patch("aswa_agents.api.agents.AgentService") as mock_service:
            mock_instance = MagicMock()
            mock_instance.get_agent = AsyncMock(return_value={
                "id": str(agent_id),
                "name": "Test Agent",
                "description": None,
                "type": "conversational",
                "status": "active",
                "version": 1,
                "system_prompt": None,
                "configuration": {},
                "actions": [],
                "triggers": [],
                "metadata": {},
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "created_by": "test-user",
                "execution_count": 0,
                "last_execution_at": None,
            })
            mock_service.return_value = mock_instance

            response = client.get(
                f"/api/v1/agents/{agent_id}",
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == str(agent_id)

    def test_get_agent_not_found(self, client, auth_headers):
        """Test getting non-existent agent."""
        with patch("aswa_agents.api.agents.AgentService") as mock_service:
            mock_instance = MagicMock()
            mock_instance.get_agent = AsyncMock(return_value=None)
            mock_service.return_value = mock_instance

            response = client.get(
                f"/api/v1/agents/{uuid4()}",
                headers=auth_headers,
            )

            assert response.status_code == 404

    def test_update_agent(self, client, auth_headers):
        """Test updating an agent."""
        agent_id = uuid4()

        with patch("aswa_agents.api.agents.AgentService") as mock_service:
            mock_instance = MagicMock()
            mock_instance.update_agent = AsyncMock(return_value={
                "id": str(agent_id),
                "name": "Updated Agent",
                "description": "Updated description",
                "type": "conversational",
                "status": "active",
                "version": 2,
                "system_prompt": None,
                "configuration": {},
                "actions": [],
                "triggers": [],
                "metadata": {},
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "created_by": "test-user",
                "execution_count": 0,
                "last_execution_at": None,
            })
            mock_service.return_value = mock_instance

            response = client.put(
                f"/api/v1/agents/{agent_id}",
                json={"name": "Updated Agent", "description": "Updated description"},
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "Updated Agent"

    def test_delete_agent(self, client, auth_headers):
        """Test deleting an agent."""
        agent_id = uuid4()

        with patch("aswa_agents.api.agents.AgentService") as mock_service:
            mock_instance = MagicMock()
            mock_instance.delete_agent = AsyncMock(return_value=True)
            mock_service.return_value = mock_instance

            response = client.delete(
                f"/api/v1/agents/{agent_id}",
                headers=auth_headers,
            )

            assert response.status_code == 200
            assert response.json()["deleted"] is True

    def test_execute_agent_sync(self, client, auth_headers):
        """Test synchronous agent execution."""
        agent_id = uuid4()
        execution_id = uuid4()

        with patch("aswa_agents.api.agents.AgentService") as mock_agent_service:
            with patch("aswa_agents.api.agents.ExecutionService") as mock_exec_service:
                mock_agent = MagicMock()
                mock_agent.get_agent = AsyncMock(return_value={
                    "id": str(agent_id),
                    "status": "active",
                })
                mock_agent_service.return_value = mock_agent

                mock_exec = MagicMock()
                mock_exec.create_execution = AsyncMock(return_value={
                    "id": str(execution_id),
                    "created_at": datetime.utcnow(),
                })
                mock_exec.run_execution = AsyncMock(return_value={
                    "id": str(execution_id),
                    "status": "completed",
                    "result": {"output": "Hello"},
                    "started_at": datetime.utcnow(),
                    "completed_at": datetime.utcnow(),
                })
                mock_exec_service.return_value = mock_exec

                response = client.post(
                    f"/api/v1/agents/{agent_id}/execute",
                    json={"input": {"message": "Hello"}, "async_execution": False},
                    headers=auth_headers,
                )

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "completed"

    def test_execute_agent_inactive(self, client, auth_headers):
        """Test executing inactive agent fails."""
        agent_id = uuid4()

        with patch("aswa_agents.api.agents.AgentService") as mock_service:
            mock_instance = MagicMock()
            mock_instance.get_agent = AsyncMock(return_value={
                "id": str(agent_id),
                "status": "draft",
            })
            mock_service.return_value = mock_instance

            response = client.post(
                f"/api/v1/agents/{agent_id}/execute",
                json={"input": {}},
                headers=auth_headers,
            )

            assert response.status_code == 400
            assert "not active" in response.json()["detail"]


class TestExecutionEndpoints:
    """Test execution API endpoints."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        return {
            "X-User-ID": "test-user",
            "X-Tenant-ID": "test-tenant",
        }

    def test_list_executions(self, client, auth_headers):
        """Test listing executions."""
        with patch("aswa_agents.api.executions.ExecutionService") as mock_service:
            mock_instance = MagicMock()
            mock_instance.list_executions = AsyncMock(return_value=(
                [{
                    "id": str(uuid4()),
                    "agent_id": str(uuid4()),
                    "status": "completed",
                    "input_data": {},
                    "result": {"output": "test"},
                    "error": None,
                    "steps": [],
                    "started_at": datetime.utcnow(),
                    "completed_at": datetime.utcnow(),
                    "duration_ms": 100,
                    "triggered_by": "test-user",
                    "trigger_type": "manual",
                    "created_at": datetime.utcnow(),
                }],
                1,
            ))
            mock_service.return_value = mock_instance

            response = client.get(
                "/api/v1/executions",
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 1

    def test_cancel_execution(self, client, auth_headers):
        """Test cancelling an execution."""
        execution_id = uuid4()

        with patch("aswa_agents.api.executions.ExecutionService") as mock_service:
            mock_instance = MagicMock()
            mock_instance.cancel_execution = AsyncMock(return_value=True)
            mock_service.return_value = mock_instance

            response = client.post(
                f"/api/v1/executions/{execution_id}/cancel",
                headers=auth_headers,
            )

            assert response.status_code == 200
            assert response.json()["cancelled"] is True


class TestHealthEndpoints:
    """Test health check endpoints."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_health_check(self, client):
        """Test basic health check."""
        response = client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_liveness_check(self, client):
        """Test liveness check."""
        response = client.get("/api/v1/health/live")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"


class TestPagination:
    """Test pagination utilities."""

    def test_pagination_params(self):
        """Test pagination parameter calculation."""
        from aswa_agents.api.pagination import PaginationParams

        params = PaginationParams(page=3, page_size=20)

        assert params.offset == 40
        assert params.limit == 20

    def test_paginated_response(self):
        """Test paginated response properties."""
        from aswa_agents.api.pagination import PaginatedResponse

        response = PaginatedResponse(
            items=["a", "b", "c"],
            total=100,
            offset=20,
            limit=20,
        )

        assert response.page == 2
        assert response.pages == 5
        assert response.has_next is True
        assert response.has_prev is True

    def test_first_page(self):
        """Test first page has no previous."""
        from aswa_agents.api.pagination import PaginatedResponse

        response = PaginatedResponse(
            items=["a"],
            total=50,
            offset=0,
            limit=20,
        )

        assert response.page == 1
        assert response.has_prev is False
        assert response.has_next is True

    def test_last_page(self):
        """Test last page has no next."""
        from aswa_agents.api.pagination import PaginatedResponse

        response = PaginatedResponse(
            items=["a"],
            total=50,
            offset=40,
            limit=20,
        )

        assert response.page == 3
        assert response.has_prev is True
        assert response.has_next is False
```

## Verification Steps

1. **Run unit tests:**
   ```bash
   cd services/agent-service
   pytest tests/unit/test_agent_api.py -v
   ```

2. **Test API endpoints:**
   ```bash
   # Health check
   curl http://localhost:8080/api/v1/health

   # Create agent
   curl -X POST http://localhost:8080/api/v1/agents \
     -H "Content-Type: application/json" \
     -H "X-User-ID: user-1" \
     -H "X-Tenant-ID: tenant-1" \
     -d '{
       "name": "My Agent",
       "description": "Test agent",
       "type": "conversational"
     }'

   # List agents
   curl http://localhost:8080/api/v1/agents \
     -H "X-Tenant-ID: tenant-1"

   # Execute agent
   curl -X POST http://localhost:8080/api/v1/agents/{id}/execute \
     -H "Content-Type: application/json" \
     -H "X-User-ID: user-1" \
     -H "X-Tenant-ID: tenant-1" \
     -d '{"input": {"message": "Hello"}}'
   ```

3. **Test with OpenAPI docs:**
   ```bash
   # Access Swagger UI
   open http://localhost:8080/docs

   # Access ReDoc
   open http://localhost:8080/redoc
   ```

4. **Run integration tests:**
   ```bash
   pytest tests/integration/test_api_integration.py -v
   ```

## API Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/agents` | GET | List agents |
| `/api/v1/agents` | POST | Create agent |
| `/api/v1/agents/{id}` | GET | Get agent |
| `/api/v1/agents/{id}` | PUT | Update agent |
| `/api/v1/agents/{id}` | DELETE | Delete agent |
| `/api/v1/agents/{id}/execute` | POST | Execute agent |
| `/api/v1/agents/{id}/deploy` | POST | Deploy agent |
| `/api/v1/agents/{id}/clone` | POST | Clone agent |
| `/api/v1/executions` | GET | List executions |
| `/api/v1/executions/{id}` | GET | Get execution |
| `/api/v1/executions/{id}/cancel` | POST | Cancel execution |
| `/api/v1/executions/{id}/retry` | POST | Retry execution |
| `/api/v1/actions` | GET | List actions |
| `/api/v1/actions` | POST | Create action |
| `/api/v1/actions/{id}/test` | POST | Test action |
| `/api/v1/triggers/webhooks` | GET/POST | Manage webhooks |
| `/api/v1/triggers/schedules` | GET/POST | Manage schedules |
| `/api/v1/webhooks/subscriptions` | GET/POST | Manage webhook subscriptions |
| `/api/v1/oauth/providers` | GET | List OAuth providers |
| `/api/v1/oauth/authorize` | POST | Start OAuth flow |
| `/api/v1/health` | GET | Health check |
| `/api/v1/health/ready` | GET | Readiness check |
| `/api/v1/health/live` | GET | Liveness check |

## Conclusion

This completes Task 9.8.4 and Phase 9 of the ASWA Agent Platform. The API provides comprehensive endpoints for:

- Agent lifecycle management (CRUD, deploy, clone, versioning)
- Execution management (run, cancel, retry, stream)
- Action management (create, test, usage tracking)
- Trigger management (webhooks, schedules)
- Webhook subscriptions for external notifications
- OAuth integration for third-party services
- Health and monitoring endpoints for Kubernetes deployment
