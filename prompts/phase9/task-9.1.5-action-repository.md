# Task 9.1.5: Action Repository

## Objective

Implement the persistence layer for agents, actions, and executions. This includes SQLAlchemy models, repositories with async support, and database migrations using Alembic.

## Prerequisites

- Task 9.1.1-9.1.4 completed
- PostgreSQL database available
- Alembic configured

## Implementation

### Step 1: SQLAlchemy Models

```python
# services/agent-service/src/aswa_agents/persistence/models.py
"""SQLAlchemy models for agent persistence."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aswa_agents.persistence.database import Base


class AgentModel(Base):
    """Persistent agent definition."""

    __tablename__ = "agents"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    # Agent definition (YAML/JSON structure)
    definition: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Status and metadata
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft", index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    tags: Mapped[list] = mapped_column(JSONB, default=list)

    # Audit fields
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Execution statistics
    last_execution_at: Mapped[datetime | None] = mapped_column(DateTime)
    execution_count: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    executions: Mapped[list["ExecutionModel"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_agent_tenant_name"),
        Index("ix_agent_tenant_status", "tenant_id", "status"),
        Index("ix_agent_tenant_created", "tenant_id", "created_at"),
    )


class ExecutionModel(Base):
    """Agent execution record."""

    __tablename__ = "executions"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    agent_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Execution status
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending", index=True
    )

    # Trigger data that started this execution
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)
    trigger_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Execution context and variables
    context: Mapped[dict] = mapped_column(JSONB, default=dict)
    variables: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Timing
    started_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(Text)
    error_details: Mapped[dict | None] = mapped_column(JSONB)

    # Flags
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    agent: Mapped["AgentModel"] = relationship(back_populates="executions")
    actions: Mapped[list["ActionModel"]] = relationship(
        back_populates="execution", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_execution_tenant_status", "tenant_id", "status"),
        Index("ix_execution_agent_started", "agent_id", "started_at"),
        Index("ix_execution_tenant_started", "tenant_id", "started_at"),
    )


class ActionModel(Base):
    """Action record within an execution."""

    __tablename__ = "actions"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    execution_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("executions.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Action definition
    action_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    target_system: Mapped[str] = mapped_column(String(50), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Planning metadata
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    reasoning: Mapped[str | None] = mapped_column(Text)
    requires_approval: Mapped[str] = mapped_column(
        String(20), nullable=False, default="review"
    )

    # Execution status
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending", index=True
    )
    sequence_order: Mapped[int] = mapped_column(Integer, default=0)

    # Result data
    result_data: Mapped[dict | None] = mapped_column(JSONB)
    external_id: Mapped[str | None] = mapped_column(String(255))
    external_url: Mapped[str | None] = mapped_column(String(1000))

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(String(50))
    error_details: Mapped[dict | None] = mapped_column(JSONB)
    retries_used: Mapped[int] = mapped_column(Integer, default=0)

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    # Approval tracking
    approved_by: Mapped[str | None] = mapped_column(String(100))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    approval_comment: Mapped[str | None] = mapped_column(Text)

    # Relationships
    execution: Mapped["ExecutionModel"] = relationship(back_populates="actions")

    __table_args__ = (
        Index("ix_action_execution_sequence", "execution_id", "sequence_order"),
        Index("ix_action_tenant_status", "tenant_id", "status"),
        Index("ix_action_awaiting_approval", "tenant_id", "status", "requires_approval"),
    )


class ApprovalModel(Base):
    """Approval request for an action."""

    __tablename__ = "approvals"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    action_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("actions.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Request details
    requested_by: Mapped[str] = mapped_column(String(100), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Reviewers
    reviewers: Mapped[list] = mapped_column(JSONB, default=list)

    # Decision
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", index=True
    )
    decided_by: Mapped[str | None] = mapped_column(String(100))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    decision_reason: Mapped[str | None] = mapped_column(Text)

    # Notification tracking
    notification_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    reminder_count: Mapped[int] = mapped_column(Integer, default=0)
    last_reminder_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (
        Index("ix_approval_tenant_status", "tenant_id", "status"),
        Index("ix_approval_pending_expires", "status", "expires_at"),
    )


class AgentTemplateModel(Base):
    """Reusable agent templates."""

    __tablename__ = "agent_templates"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )

    # Template metadata
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="general")
    icon: Mapped[str] = mapped_column(String(50), default="bot")

    # Template definition
    definition: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Template variables for customization
    variables: Mapped[list] = mapped_column(JSONB, default=list)

    # Visibility
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    tenant_id: Mapped[str | None] = mapped_column(String(100), index=True)

    # Usage statistics
    usage_count: Mapped[int] = mapped_column(Integer, default=0)

    # Audit
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_template_category", "category"),
        Index("ix_template_tenant_public", "tenant_id", "is_public"),
    )
```

### Step 2: Agent Repository

```python
# services/agent-service/src/aswa_agents/persistence/repository.py
"""Repository classes for data access."""

from datetime import datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import func, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from aswa_agents.api.schemas import AgentCreate, AgentUpdate
from aswa_agents.core.models import ActionContext, ActionResult, ExecutionResult
from aswa_agents.core.types import ActionStatus
from aswa_agents.persistence.models import (
    AgentModel,
    ExecutionModel,
    ActionModel,
    ApprovalModel,
    AgentTemplateModel,
)

logger = structlog.get_logger()


class AgentRepository:
    """Repository for agent CRUD operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self._logger = logger.bind(repository="AgentRepository")

    async def create(
        self,
        tenant_id: str,
        data: AgentCreate,
        created_by: str = "system",
    ) -> AgentModel:
        """Create a new agent."""
        agent = AgentModel(
            tenant_id=tenant_id,
            name=data.name,
            display_name=data.display_name,
            description=data.description,
            definition=data.definition.model_dump(),
            tags=data.tags,
            created_by=created_by,
        )
        self.session.add(agent)
        await self.session.flush()
        await self.session.refresh(agent)

        self._logger.info(
            "Created agent",
            agent_id=str(agent.id),
            tenant_id=tenant_id,
            name=data.name,
        )
        return agent

    async def get(
        self,
        agent_id: UUID,
        tenant_id: str,
    ) -> AgentModel | None:
        """Get agent by ID."""
        result = await self.session.execute(
            select(AgentModel).where(
                AgentModel.id == agent_id,
                AgentModel.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_name(
        self,
        name: str,
        tenant_id: str,
    ) -> AgentModel | None:
        """Get agent by name."""
        result = await self.session.execute(
            select(AgentModel).where(
                AgentModel.name == name,
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
    ) -> tuple[list[AgentModel], int]:
        """List agents with pagination."""
        query = select(AgentModel).where(AgentModel.tenant_id == tenant_id)

        if status:
            query = query.where(AgentModel.status == status)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.session.scalar(count_query) or 0

        # Get paginated results
        query = query.order_by(AgentModel.created_at.desc())
        query = query.limit(limit).offset(offset)

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

        update_data = data.model_dump(exclude_unset=True)

        if "definition" in update_data and update_data["definition"]:
            update_data["definition"] = update_data["definition"].model_dump()

        for key, value in update_data.items():
            if value is not None:
                setattr(agent, key, value)

        agent.version += 1
        await self.session.flush()
        await self.session.refresh(agent)

        self._logger.info(
            "Updated agent",
            agent_id=str(agent_id),
            version=agent.version,
        )
        return agent

    async def delete(
        self,
        agent_id: UUID,
        tenant_id: str,
    ) -> bool:
        """Delete an agent."""
        result = await self.session.execute(
            delete(AgentModel).where(
                AgentModel.id == agent_id,
                AgentModel.tenant_id == tenant_id,
            )
        )
        deleted = result.rowcount > 0

        if deleted:
            self._logger.info("Deleted agent", agent_id=str(agent_id))

        return deleted

    async def update_execution_stats(
        self,
        agent_id: UUID,
        success: bool,
    ) -> None:
        """Update agent execution statistics."""
        stmt = (
            update(AgentModel)
            .where(AgentModel.id == agent_id)
            .values(
                execution_count=AgentModel.execution_count + 1,
                success_count=AgentModel.success_count + (1 if success else 0),
                failure_count=AgentModel.failure_count + (0 if success else 1),
                last_execution_at=datetime.utcnow(),
            )
        )
        await self.session.execute(stmt)


class ExecutionRepository:
    """Repository for execution records."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self._logger = logger.bind(repository="ExecutionRepository")

    async def save(self, execution: ExecutionResult) -> ExecutionModel:
        """Save execution record."""
        model = ExecutionModel(
            id=execution.execution_id,
            agent_id=execution.agent_id,
            tenant_id=execution.tenant_id,
            status=execution.status.value,
            trigger_type=execution.trigger_data.trigger_type.value,
            trigger_data=execution.trigger_data.model_dump(),
            started_at=execution.started_at,
            dry_run=execution.dry_run,
        )
        self.session.add(model)
        await self.session.flush()

        self._logger.debug(
            "Saved execution",
            execution_id=str(execution.execution_id),
        )
        return model

    async def update(self, execution: ExecutionResult) -> None:
        """Update execution record."""
        stmt = (
            update(ExecutionModel)
            .where(ExecutionModel.id == execution.execution_id)
            .values(
                status=execution.status.value,
                variables=execution.variables,
                completed_at=execution.completed_at,
                duration_ms=execution.total_duration_ms,
                error_message=execution.error_message,
            )
        )
        await self.session.execute(stmt)

    async def get(self, execution_id: UUID) -> ExecutionResult | None:
        """Get execution by ID."""
        result = await self.session.execute(
            select(ExecutionModel).where(ExecutionModel.id == execution_id)
        )
        model = result.scalar_one_or_none()

        if not model:
            return None

        from aswa_agents.core.models import TriggerData

        return ExecutionResult(
            execution_id=model.id,
            agent_id=model.agent_id,
            tenant_id=model.tenant_id,
            status=ActionStatus(model.status),
            trigger_data=TriggerData(**model.trigger_data),
            variables=model.variables or {},
            started_at=model.started_at,
            completed_at=model.completed_at,
            total_duration_ms=model.duration_ms,
            error_message=model.error_message,
            dry_run=model.dry_run,
        )

    async def list_by_agent(
        self,
        agent_id: UUID,
        tenant_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ExecutionModel]:
        """List executions for an agent."""
        result = await self.session.execute(
            select(ExecutionModel)
            .where(
                ExecutionModel.agent_id == agent_id,
                ExecutionModel.tenant_id == tenant_id,
            )
            .order_by(ExecutionModel.started_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def list_by_tenant(
        self,
        tenant_id: str,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ExecutionModel], int]:
        """List executions for a tenant."""
        query = select(ExecutionModel).where(ExecutionModel.tenant_id == tenant_id)

        if status:
            query = query.where(ExecutionModel.status == status)

        count_query = select(func.count()).select_from(query.subquery())
        total = await self.session.scalar(count_query) or 0

        query = query.order_by(ExecutionModel.started_at.desc())
        query = query.limit(limit).offset(offset)

        result = await self.session.execute(query)
        return list(result.scalars().all()), total


class ActionRepository:
    """Repository for action records."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self._logger = logger.bind(repository="ActionRepository")

    async def save(
        self,
        action: Any,
        agent_name: str,
        context: ActionContext,
    ) -> ActionModel:
        """Save action record."""
        model = ActionModel(
            id=action.id,
            execution_id=context.execution_id,
            tenant_id=context.tenant_id,
            action_type=action.type.value,
            target_system=action.target_system,
            parameters=action.parameters,
            confidence=action.confidence,
            reasoning=action.reasoning,
            requires_approval=action.requires_approval.value if hasattr(action.requires_approval, 'value') else str(action.requires_approval),
        )
        self.session.add(model)
        await self.session.flush()

        self._logger.debug(
            "Saved action",
            action_id=str(action.id),
            action_type=action.type.value,
        )
        return model

    async def get(self, action_id: UUID) -> dict | None:
        """Get action by ID with execution context."""
        result = await self.session.execute(
            select(ActionModel).where(ActionModel.id == action_id)
        )
        model = result.scalar_one_or_none()

        if not model:
            return None

        # Get execution for context
        exec_result = await self.session.execute(
            select(ExecutionModel).where(ExecutionModel.id == model.execution_id)
        )
        execution = exec_result.scalar_one_or_none()

        # Get agent name
        agent_result = await self.session.execute(
            select(AgentModel.name).where(AgentModel.id == execution.agent_id)
        )
        agent_name = agent_result.scalar_one_or_none()

        return {
            "status": model.status,
            "agent_name": agent_name,
            "agent_config": {},
            "action": {
                "id": str(model.id),
                "type": model.action_type,
                "target_system": model.target_system,
                "confidence": model.confidence,
                "parameters": model.parameters,
            },
            "context": {
                "execution_id": str(model.execution_id),
                "agent_id": str(execution.agent_id),
                "agent_name": agent_name,
                "tenant_id": model.tenant_id,
                "trigger_data": execution.trigger_data,
            },
        }

    async def update_status(
        self,
        action_id: UUID,
        status: ActionStatus,
    ) -> None:
        """Update action status."""
        values: dict[str, Any] = {"status": status.value}

        if status == ActionStatus.EXECUTING:
            values["started_at"] = datetime.utcnow()

        stmt = update(ActionModel).where(ActionModel.id == action_id).values(**values)
        await self.session.execute(stmt)

    async def update_result(
        self,
        action_id: UUID,
        result: ActionResult,
    ) -> None:
        """Update action with execution result."""
        stmt = (
            update(ActionModel)
            .where(ActionModel.id == action_id)
            .values(
                status=result.status.value,
                result_data=result.result_data,
                external_id=result.external_id,
                external_url=result.external_url,
                error_message=result.error_message,
                error_code=result.error_code,
                error_details=result.error_details,
                retries_used=result.retries_used,
                completed_at=result.completed_at,
                duration_ms=result.execution_time_ms,
            )
        )
        await self.session.execute(stmt)

    async def list_pending_approvals(
        self,
        tenant_id: str,
        limit: int = 50,
    ) -> list[ActionModel]:
        """List actions awaiting approval."""
        result = await self.session.execute(
            select(ActionModel)
            .where(
                ActionModel.tenant_id == tenant_id,
                ActionModel.status == ActionStatus.AWAITING_APPROVAL.value,
            )
            .order_by(ActionModel.started_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def approve(
        self,
        action_id: UUID,
        approved_by: str,
        comment: str | None = None,
    ) -> bool:
        """Approve an action."""
        stmt = (
            update(ActionModel)
            .where(
                ActionModel.id == action_id,
                ActionModel.status == ActionStatus.AWAITING_APPROVAL.value,
            )
            .values(
                status=ActionStatus.APPROVED.value,
                approved_by=approved_by,
                approved_at=datetime.utcnow(),
                approval_comment=comment,
            )
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def reject(
        self,
        action_id: UUID,
        rejected_by: str,
        reason: str,
    ) -> bool:
        """Reject an action."""
        stmt = (
            update(ActionModel)
            .where(
                ActionModel.id == action_id,
                ActionModel.status == ActionStatus.AWAITING_APPROVAL.value,
            )
            .values(
                status=ActionStatus.REJECTED.value,
                approved_by=rejected_by,
                approved_at=datetime.utcnow(),
                approval_comment=reason,
            )
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0


class TemplateRepository:
    """Repository for agent templates."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, template_id: UUID) -> AgentTemplateModel | None:
        """Get template by ID."""
        result = await self.session.execute(
            select(AgentTemplateModel).where(AgentTemplateModel.id == template_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> AgentTemplateModel | None:
        """Get template by name."""
        result = await self.session.execute(
            select(AgentTemplateModel).where(AgentTemplateModel.name == name)
        )
        return result.scalar_one_or_none()

    async def list_available(
        self,
        tenant_id: str,
        category: str | None = None,
    ) -> list[AgentTemplateModel]:
        """List templates available to a tenant."""
        query = select(AgentTemplateModel).where(
            (AgentTemplateModel.is_builtin == True) |
            (AgentTemplateModel.is_public == True) |
            (AgentTemplateModel.tenant_id == tenant_id)
        )

        if category:
            query = query.where(AgentTemplateModel.category == category)

        query = query.order_by(
            AgentTemplateModel.is_builtin.desc(),
            AgentTemplateModel.usage_count.desc(),
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def increment_usage(self, template_id: UUID) -> None:
        """Increment template usage count."""
        stmt = (
            update(AgentTemplateModel)
            .where(AgentTemplateModel.id == template_id)
            .values(usage_count=AgentTemplateModel.usage_count + 1)
        )
        await self.session.execute(stmt)
```

### Step 3: Alembic Migration

```python
# services/agent-service/alembic/versions/001_initial_schema.py
"""Initial schema for agent service.

Revision ID: 001
Revises:
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Agents table
    op.create_table(
        'agents',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', sa.String(100), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('display_name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('definition', postgresql.JSONB(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('tags', postgresql.JSONB(), nullable=True, server_default='[]'),
        sa.Column('created_by', sa.String(100), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('last_execution_at', sa.DateTime(), nullable=True),
        sa.Column('execution_count', sa.Integer(), server_default='0'),
        sa.Column('success_count', sa.Integer(), server_default='0'),
        sa.Column('failure_count', sa.Integer(), server_default='0'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'name', name='uq_agent_tenant_name'),
    )
    op.create_index('ix_agents_tenant_id', 'agents', ['tenant_id'])
    op.create_index('ix_agents_status', 'agents', ['status'])
    op.create_index('ix_agent_tenant_status', 'agents', ['tenant_id', 'status'])
    op.create_index('ix_agent_tenant_created', 'agents', ['tenant_id', 'created_at'])

    # Executions table
    op.create_table(
        'executions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', sa.String(100), nullable=False),
        sa.Column('status', sa.String(30), nullable=False, server_default='pending'),
        sa.Column('trigger_type', sa.String(50), nullable=False),
        sa.Column('trigger_data', postgresql.JSONB(), nullable=False),
        sa.Column('context', postgresql.JSONB(), nullable=True),
        sa.Column('variables', postgresql.JSONB(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_details', postgresql.JSONB(), nullable=True),
        sa.Column('dry_run', sa.Boolean(), server_default='false'),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_executions_tenant_id', 'executions', ['tenant_id'])
    op.create_index('ix_executions_status', 'executions', ['status'])
    op.create_index('ix_execution_tenant_status', 'executions', ['tenant_id', 'status'])
    op.create_index('ix_execution_agent_started', 'executions', ['agent_id', 'started_at'])
    op.create_index('ix_execution_tenant_started', 'executions', ['tenant_id', 'started_at'])

    # Actions table
    op.create_table(
        'actions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('execution_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', sa.String(100), nullable=False),
        sa.Column('action_type', sa.String(50), nullable=False),
        sa.Column('target_system', sa.String(50), nullable=False),
        sa.Column('parameters', postgresql.JSONB(), nullable=True),
        sa.Column('confidence', sa.Float(), server_default='1.0'),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('requires_approval', sa.String(20), nullable=False, server_default='review'),
        sa.Column('status', sa.String(30), nullable=False, server_default='pending'),
        sa.Column('sequence_order', sa.Integer(), server_default='0'),
        sa.Column('result_data', postgresql.JSONB(), nullable=True),
        sa.Column('external_id', sa.String(255), nullable=True),
        sa.Column('external_url', sa.String(1000), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_code', sa.String(50), nullable=True),
        sa.Column('error_details', postgresql.JSONB(), nullable=True),
        sa.Column('retries_used', sa.Integer(), server_default='0'),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('approved_by', sa.String(100), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('approval_comment', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['execution_id'], ['executions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_actions_tenant_id', 'actions', ['tenant_id'])
    op.create_index('ix_actions_action_type', 'actions', ['action_type'])
    op.create_index('ix_actions_status', 'actions', ['status'])
    op.create_index('ix_action_execution_sequence', 'actions', ['execution_id', 'sequence_order'])
    op.create_index('ix_action_tenant_status', 'actions', ['tenant_id', 'status'])
    op.create_index('ix_action_awaiting_approval', 'actions', ['tenant_id', 'status', 'requires_approval'])

    # Approvals table
    op.create_table(
        'approvals',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', sa.String(100), nullable=False),
        sa.Column('requested_by', sa.String(100), nullable=False),
        sa.Column('requested_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('reviewers', postgresql.JSONB(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('decided_by', sa.String(100), nullable=True),
        sa.Column('decided_at', sa.DateTime(), nullable=True),
        sa.Column('decision_reason', sa.Text(), nullable=True),
        sa.Column('notification_sent', sa.Boolean(), server_default='false'),
        sa.Column('reminder_count', sa.Integer(), server_default='0'),
        sa.Column('last_reminder_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['action_id'], ['actions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_approvals_tenant_id', 'approvals', ['tenant_id'])
    op.create_index('ix_approvals_status', 'approvals', ['status'])
    op.create_index('ix_approval_tenant_status', 'approvals', ['tenant_id', 'status'])
    op.create_index('ix_approval_pending_expires', 'approvals', ['status', 'expires_at'])

    # Agent templates table
    op.create_table(
        'agent_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('display_name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(50), nullable=False, server_default='general'),
        sa.Column('icon', sa.String(50), server_default='bot'),
        sa.Column('definition', postgresql.JSONB(), nullable=False),
        sa.Column('variables', postgresql.JSONB(), nullable=True, server_default='[]'),
        sa.Column('is_builtin', sa.Boolean(), server_default='false'),
        sa.Column('is_public', sa.Boolean(), server_default='false'),
        sa.Column('tenant_id', sa.String(100), nullable=True),
        sa.Column('usage_count', sa.Integer(), server_default='0'),
        sa.Column('created_by', sa.String(100), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_index('ix_agent_templates_tenant_id', 'agent_templates', ['tenant_id'])
    op.create_index('ix_template_category', 'agent_templates', ['category'])
    op.create_index('ix_template_tenant_public', 'agent_templates', ['tenant_id', 'is_public'])


def downgrade() -> None:
    op.drop_table('agent_templates')
    op.drop_table('approvals')
    op.drop_table('actions')
    op.drop_table('executions')
    op.drop_table('agents')
```

### Step 4: Alembic Configuration

```ini
# services/agent-service/alembic.ini
[alembic]
script_location = alembic
prepend_sys_path = .
version_path_separator = os

sqlalchemy.url = driver://user:pass@localhost/dbname

[post_write_hooks]

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

```python
# services/agent-service/alembic/env.py
"""Alembic environment configuration."""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from aswa_agents.config import get_settings
from aswa_agents.persistence.database import Base
from aswa_agents.persistence.models import *  # noqa: Import all models

config = context.config
settings = get_settings()

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url():
    """Get database URL from settings."""
    return str(settings.database_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with connection."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in async mode."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

## Test Cases

```python
# services/agent-service/tests/unit/test_repository.py
"""Tests for repository classes."""

import pytest
from datetime import datetime
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from aswa_agents.persistence.repository import (
    AgentRepository,
    ExecutionRepository,
    ActionRepository,
)
from aswa_agents.persistence.models import AgentModel, ExecutionModel, ActionModel
from aswa_agents.api.schemas import (
    AgentCreate,
    AgentUpdate,
    AgentDefinition,
    TriggerConfig,
    ActionConfig,
)
from aswa_agents.core.models import ExecutionResult, TriggerData, ActionResult
from aswa_agents.core.types import ActionStatus, TriggerType


@pytest.fixture
def mock_session():
    """Create mock async session."""
    session = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    session.scalar = AsyncMock()
    return session


@pytest.fixture
def sample_agent_create():
    """Create sample agent data."""
    return AgentCreate(
        name="test-agent",
        display_name="Test Agent",
        description="A test agent",
        definition=AgentDefinition(
            trigger=TriggerConfig(type="manual"),
            actions=[ActionConfig(id="action1", type="log")],
        ),
        tags=["test"],
    )


class TestAgentRepository:
    """Test AgentRepository class."""

    async def test_create_agent(self, mock_session, sample_agent_create):
        """Test creating an agent."""
        repo = AgentRepository(mock_session)

        # Mock the add to capture the agent
        added_agent = None
        def capture_add(agent):
            nonlocal added_agent
            added_agent = agent
        mock_session.add = capture_add

        await repo.create(
            tenant_id="test-tenant",
            data=sample_agent_create,
            created_by="test-user",
        )

        assert added_agent is not None
        assert added_agent.name == "test-agent"
        assert added_agent.tenant_id == "test-tenant"

    async def test_get_agent(self, mock_session):
        """Test getting an agent by ID."""
        agent_id = uuid4()
        mock_agent = MagicMock(spec=AgentModel)
        mock_agent.id = agent_id
        mock_agent.name = "test"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_agent
        mock_session.execute.return_value = mock_result

        repo = AgentRepository(mock_session)
        result = await repo.get(agent_id, "test-tenant")

        assert result is not None
        assert result.id == agent_id

    async def test_get_agent_not_found(self, mock_session):
        """Test getting non-existent agent."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        repo = AgentRepository(mock_session)
        result = await repo.get(uuid4(), "test-tenant")

        assert result is None

    async def test_list_agents(self, mock_session):
        """Test listing agents."""
        mock_agents = [MagicMock(spec=AgentModel) for _ in range(3)]

        # Mock count query
        mock_session.scalar.return_value = 3

        # Mock list query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_agents
        mock_session.execute.return_value = mock_result

        repo = AgentRepository(mock_session)
        agents, total = await repo.list("test-tenant")

        assert len(agents) == 3
        assert total == 3

    async def test_delete_agent(self, mock_session):
        """Test deleting an agent."""
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result

        repo = AgentRepository(mock_session)
        result = await repo.delete(uuid4(), "test-tenant")

        assert result is True

    async def test_delete_agent_not_found(self, mock_session):
        """Test deleting non-existent agent."""
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_session.execute.return_value = mock_result

        repo = AgentRepository(mock_session)
        result = await repo.delete(uuid4(), "test-tenant")

        assert result is False


class TestExecutionRepository:
    """Test ExecutionRepository class."""

    async def test_save_execution(self, mock_session):
        """Test saving an execution."""
        execution = ExecutionResult(
            execution_id=uuid4(),
            agent_id=uuid4(),
            tenant_id="test-tenant",
            status=ActionStatus.PENDING,
            trigger_data=TriggerData(trigger_type=TriggerType.MANUAL),
            started_at=datetime.utcnow(),
        )

        added_model = None
        def capture_add(model):
            nonlocal added_model
            added_model = model
        mock_session.add = capture_add

        repo = ExecutionRepository(mock_session)
        await repo.save(execution)

        assert added_model is not None
        assert added_model.id == execution.execution_id

    async def test_update_execution(self, mock_session):
        """Test updating an execution."""
        execution = ExecutionResult(
            execution_id=uuid4(),
            agent_id=uuid4(),
            tenant_id="test-tenant",
            status=ActionStatus.COMPLETED,
            trigger_data=TriggerData(trigger_type=TriggerType.MANUAL),
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )

        repo = ExecutionRepository(mock_session)
        await repo.update(execution)

        mock_session.execute.assert_called_once()


class TestActionRepository:
    """Test ActionRepository class."""

    async def test_update_status(self, mock_session):
        """Test updating action status."""
        repo = ActionRepository(mock_session)
        await repo.update_status(uuid4(), ActionStatus.EXECUTING)

        mock_session.execute.assert_called_once()

    async def test_approve_action(self, mock_session):
        """Test approving an action."""
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result

        repo = ActionRepository(mock_session)
        result = await repo.approve(uuid4(), "approver", "Looks good")

        assert result is True

    async def test_reject_action(self, mock_session):
        """Test rejecting an action."""
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result

        repo = ActionRepository(mock_session)
        result = await repo.reject(uuid4(), "reviewer", "Not appropriate")

        assert result is True
```

```python
# services/agent-service/tests/integration/test_repository_integration.py
"""Integration tests for repositories with real database."""

import pytest
from uuid import uuid4

from aswa_agents.persistence.repository import (
    AgentRepository,
    ExecutionRepository,
    ActionRepository,
)
from aswa_agents.api.schemas import (
    AgentCreate,
    AgentUpdate,
    AgentDefinition,
    TriggerConfig,
    ActionConfig,
    AgentStatus,
)


@pytest.mark.integration
class TestAgentRepositoryIntegration:
    """Integration tests for AgentRepository."""

    async def test_full_agent_lifecycle(self, db_session, test_tenant_id):
        """Test complete agent CRUD cycle."""
        repo = AgentRepository(db_session)

        # Create
        agent_data = AgentCreate(
            name="integration-test-agent",
            display_name="Integration Test Agent",
            description="Testing the full lifecycle",
            definition=AgentDefinition(
                trigger=TriggerConfig(type="manual"),
                actions=[ActionConfig(id="a1", type="log", config={"msg": "test"})],
            ),
            tags=["integration", "test"],
        )

        agent = await repo.create(
            tenant_id=test_tenant_id,
            data=agent_data,
            created_by="test-user",
        )
        assert agent.id is not None
        assert agent.status == "draft"
        assert agent.version == 1

        # Read
        fetched = await repo.get(agent.id, test_tenant_id)
        assert fetched is not None
        assert fetched.name == "integration-test-agent"

        # Update
        update_data = AgentUpdate(
            display_name="Updated Agent",
            status=AgentStatus.ACTIVE,
        )
        updated = await repo.update(agent.id, test_tenant_id, update_data)
        assert updated.display_name == "Updated Agent"
        assert updated.status == "active"
        assert updated.version == 2

        # List
        agents, total = await repo.list(test_tenant_id)
        assert total >= 1
        assert any(a.id == agent.id for a in agents)

        # Delete
        deleted = await repo.delete(agent.id, test_tenant_id)
        assert deleted is True

        # Verify deleted
        fetched_after = await repo.get(agent.id, test_tenant_id)
        assert fetched_after is None

    async def test_list_with_status_filter(self, db_session, test_tenant_id):
        """Test listing agents with status filter."""
        repo = AgentRepository(db_session)

        # Create agents with different statuses
        for status in ["draft", "active", "paused"]:
            agent_data = AgentCreate(
                name=f"filter-test-{status}",
                display_name=f"Filter Test {status}",
                definition=AgentDefinition(
                    trigger=TriggerConfig(type="manual"),
                    actions=[],
                ),
            )
            agent = await repo.create(test_tenant_id, agent_data)
            if status != "draft":
                await repo.update(
                    agent.id,
                    test_tenant_id,
                    AgentUpdate(status=AgentStatus(status)),
                )

        # Filter by status
        active_agents, _ = await repo.list(test_tenant_id, status="active")
        assert all(a.status == "active" for a in active_agents)

    async def test_tenant_isolation(self, db_session):
        """Test that agents are isolated by tenant."""
        repo = AgentRepository(db_session)
        tenant_a = f"tenant-a-{uuid4().hex[:8]}"
        tenant_b = f"tenant-b-{uuid4().hex[:8]}"

        # Create agent in tenant A
        agent_data = AgentCreate(
            name="isolated-agent",
            display_name="Isolated Agent",
            definition=AgentDefinition(
                trigger=TriggerConfig(type="manual"),
                actions=[],
            ),
        )
        agent_a = await repo.create(tenant_a, agent_data)

        # Try to access from tenant B
        fetched = await repo.get(agent_a.id, tenant_b)
        assert fetched is None

        # List should be empty for tenant B
        agents_b, total_b = await repo.list(tenant_b)
        assert total_b == 0


@pytest.mark.integration
class TestExecutionRepositoryIntegration:
    """Integration tests for ExecutionRepository."""

    async def test_save_and_retrieve_execution(self, db_session, test_tenant_id):
        """Test saving and retrieving execution."""
        from aswa_agents.core.models import ExecutionResult, TriggerData
        from aswa_agents.core.types import ActionStatus, TriggerType

        # First create an agent
        agent_repo = AgentRepository(db_session)
        agent_data = AgentCreate(
            name="execution-test-agent",
            display_name="Execution Test",
            definition=AgentDefinition(
                trigger=TriggerConfig(type="manual"),
                actions=[],
            ),
        )
        agent = await agent_repo.create(test_tenant_id, agent_data)

        # Create execution
        execution = ExecutionResult(
            execution_id=uuid4(),
            agent_id=agent.id,
            tenant_id=test_tenant_id,
            status=ActionStatus.PENDING,
            trigger_data=TriggerData(trigger_type=TriggerType.MANUAL),
            started_at=datetime.utcnow(),
        )

        exec_repo = ExecutionRepository(db_session)
        await exec_repo.save(execution)

        # Retrieve
        fetched = await exec_repo.get(execution.execution_id)
        assert fetched is not None
        assert fetched.agent_id == agent.id
        assert fetched.status == ActionStatus.PENDING
```

## Verification Steps

1. **Run migrations:**
   ```bash
   cd services/agent-service
   alembic upgrade head
   ```

2. **Run unit tests:**
   ```bash
   pytest tests/unit/test_repository.py -v
   ```

3. **Run integration tests:**
   ```bash
   pytest tests/integration/test_repository_integration.py -v --integration
   ```

4. **Verify schema:**
   ```bash
   psql -h localhost -U aswa -d aswa_agents -c "\dt"
   ```

5. **Check indexes:**
   ```bash
   psql -h localhost -U aswa -d aswa_agents -c "\di"
   ```

## Next Task

Proceed to `task-9.2.1-intent-extraction.md` to implement NLP intent extraction.
