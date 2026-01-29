"""Agent persistence repository."""

from datetime import datetime, timezone
from typing import Tuple
from uuid import UUID, uuid4

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from aswa_agents.api.schemas import AgentCreate, AgentUpdate, AgentStatus
from aswa_agents.persistence.models import AgentModel


class AgentRepository:
    """Repository for agent persistence operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, tenant_id: str, data: AgentCreate) -> AgentModel:
        """Create a new agent."""
        now = datetime.now(timezone.utc)
        agent = AgentModel(
            id=uuid4(),
            tenant_id=tenant_id,
            name=data.name,
            display_name=data.display_name,
            description=data.description,
            definition=data.definition.model_dump(),
            status=AgentStatus.DRAFT,
            tags=data.tags,
            created_by="system",  # TODO: Get from context
            created_at=now,
            updated_at=now,
            execution_count=0,
            success_count=0,
            failure_count=0,
        )
        self.session.add(agent)
        await self.session.flush()
        return agent

    async def get(self, agent_id: UUID, tenant_id: str) -> AgentModel | None:
        """Get an agent by ID."""
        result = await self.session.execute(
            select(AgentModel).where(
                AgentModel.id == agent_id,
                AgentModel.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        tenant_id: str,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[list[AgentModel], int]:
        """List agents for a tenant."""
        query = select(AgentModel).where(AgentModel.tenant_id == tenant_id)

        if status:
            query = query.where(AgentModel.status == status)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        # Get paginated results
        query = query.offset(offset).limit(limit).order_by(AgentModel.created_at.desc())
        result = await self.session.execute(query)
        agents = list(result.scalars().all())

        return agents, total

    async def update(
        self,
        agent_id: UUID,
        tenant_id: str,
        data: AgentUpdate,
    ) -> AgentModel | None:
        """Update an agent."""
        agent = await self.get(agent_id, tenant_id)
        if not agent:
            return None

        if data.display_name is not None:
            agent.display_name = data.display_name
        if data.description is not None:
            agent.description = data.description
        if data.definition is not None:
            agent.definition = data.definition.model_dump()
        if data.status is not None:
            agent.status = data.status
        if data.tags is not None:
            agent.tags = data.tags

        agent.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return agent

    async def delete(self, agent_id: UUID, tenant_id: str) -> bool:
        """Delete an agent."""
        agent = await self.get(agent_id, tenant_id)
        if not agent:
            return False

        await self.session.delete(agent)
        await self.session.flush()
        return True
