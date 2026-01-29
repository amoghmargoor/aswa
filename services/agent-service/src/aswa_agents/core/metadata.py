"""Agent metadata models for registry responses."""

from pydantic import BaseModel, Field


class AgentMetadata(BaseModel):
    """Metadata about a registered agent."""

    name: str = Field(..., description="Agent class name")
    version: str = Field(..., description="Agent version")
    description: str = Field(..., description="Agent description")
    supported_trigger_types: list[str] = Field(
        default_factory=list,
        description="List of trigger types this agent can handle",
    )
    required_permissions: list[str] = Field(
        default_factory=list,
        description="List of permissions required by this agent",
    )
    required_connectors: list[str] = Field(
        default_factory=list,
        description="List of connectors required by this agent",
    )

    model_config = {"frozen": True}


class AgentListResponse(BaseModel):
    """Response for listing agents."""

    agents: list[AgentMetadata] = Field(
        default_factory=list,
        description="List of registered agents",
    )
    total: int = Field(..., description="Total number of agents")
