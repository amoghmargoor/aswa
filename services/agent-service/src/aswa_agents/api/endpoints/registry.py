"""Registry API endpoints for agent discovery."""

from fastapi import APIRouter, HTTPException, Query

import structlog

from aswa_agents.core.registry import AgentRegistry
from aswa_agents.core.metadata import AgentMetadata, AgentListResponse

logger = structlog.get_logger()
router = APIRouter(prefix="/registry", tags=["registry"])


@router.get("/agents", response_model=AgentListResponse)
async def list_registered_agents() -> AgentListResponse:
    """
    List all registered agents with their metadata.

    Returns metadata for all agents currently registered in the system.
    """
    AgentRegistry.initialize()

    agents_data = AgentRegistry.list_agents()
    agents = [
        AgentMetadata(
            name=agent["name"],
            version=agent["version"],
            description=agent["description"],
            supported_trigger_types=agent["supported_trigger_types"],
            required_permissions=agent["required_permissions"],
            required_connectors=agent["required_connectors"],
        )
        for agent in agents_data
    ]

    return AgentListResponse(
        agents=agents,
        total=len(agents),
    )


@router.get("/agents/{agent_name}", response_model=AgentMetadata)
async def get_agent_info(agent_name: str) -> AgentMetadata:
    """
    Get metadata for a specific agent.

    Args:
        agent_name: The name of the agent class

    Returns:
        Agent metadata

    Raises:
        HTTPException: If agent not found
    """
    AgentRegistry.initialize()

    agent_class = AgentRegistry.get_agent_class(agent_name)
    if not agent_class:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_name}' not found",
        )

    instance = agent_class({})
    return AgentMetadata(
        name=agent_name,
        version=instance.version,
        description=instance.description,
        supported_trigger_types=instance.supported_trigger_types,
        required_permissions=instance.required_permissions,
        required_connectors=instance.required_connectors,
    )


@router.get("/agents/by-trigger/{trigger_type}", response_model=AgentListResponse)
async def list_agents_by_trigger(
    trigger_type: str,
    tenant_id: str = Query(default="default", description="Tenant ID for filtering"),
) -> AgentListResponse:
    """
    List agents that support a specific trigger type.

    Args:
        trigger_type: The trigger type to filter by
        tenant_id: Optional tenant ID for tenant-specific filtering

    Returns:
        List of agents supporting the trigger type
    """
    AgentRegistry.initialize()

    # Build tenant config - in production this would come from database
    tenant_config = {"tenant_id": tenant_id}

    # Get all agents that support this trigger type
    agents_data = AgentRegistry.list_agents()
    matching_agents = [
        AgentMetadata(
            name=agent["name"],
            version=agent["version"],
            description=agent["description"],
            supported_trigger_types=agent["supported_trigger_types"],
            required_permissions=agent["required_permissions"],
            required_connectors=agent["required_connectors"],
        )
        for agent in agents_data
        if trigger_type in agent["supported_trigger_types"]
    ]

    return AgentListResponse(
        agents=matching_agents,
        total=len(matching_agents),
    )


@router.get("/agents/by-connector/{connector_id}", response_model=AgentListResponse)
async def list_agents_by_connector(connector_id: str) -> AgentListResponse:
    """
    List agents that require a specific connector.

    Args:
        connector_id: The connector ID to filter by (e.g., "jira", "slack")

    Returns:
        List of agents requiring the connector
    """
    AgentRegistry.initialize()

    agent_classes = AgentRegistry.find_agents_by_connector(connector_id)

    agents = []
    for agent_class in agent_classes:
        instance = agent_class({})
        agents.append(
            AgentMetadata(
                name=agent_class.__name__,
                version=instance.version,
                description=instance.description,
                supported_trigger_types=instance.supported_trigger_types,
                required_permissions=instance.required_permissions,
                required_connectors=instance.required_connectors,
            )
        )

    return AgentListResponse(
        agents=agents,
        total=len(agents),
    )


@router.get("/agents/by-permission/{permission}", response_model=AgentListResponse)
async def list_agents_by_permission(permission: str) -> AgentListResponse:
    """
    List agents that require a specific permission.

    Args:
        permission: The permission string to filter by (e.g., "jira:write")

    Returns:
        List of agents requiring the permission
    """
    AgentRegistry.initialize()

    agent_classes = AgentRegistry.find_agents_by_permission(permission)

    agents = []
    for agent_class in agent_classes:
        instance = agent_class({})
        agents.append(
            AgentMetadata(
                name=agent_class.__name__,
                version=instance.version,
                description=instance.description,
                supported_trigger_types=instance.supported_trigger_types,
                required_permissions=instance.required_permissions,
                required_connectors=instance.required_connectors,
            )
        )

    return AgentListResponse(
        agents=agents,
        total=len(agents),
    )


@router.post("/agents/{agent_name}/validate")
async def validate_agent_config(
    agent_name: str,
    config: dict,
) -> dict:
    """
    Validate configuration for an agent.

    Args:
        agent_name: The name of the agent class
        config: Configuration to validate

    Returns:
        Validation result with is_valid and errors
    """
    AgentRegistry.initialize()

    is_valid, errors = AgentRegistry.validate_agent_config(agent_name, config)

    return {
        "is_valid": is_valid,
        "errors": errors,
    }


@router.get("/stats")
async def get_registry_stats() -> dict:
    """
    Get registry statistics.

    Returns:
        Statistics about the registry
    """
    AgentRegistry.initialize()

    return {
        "total_agents": AgentRegistry.count(),
        "is_initialized": AgentRegistry.is_initialized(),
        "agents": list(AgentRegistry.get_all_agents().keys()),
    }
