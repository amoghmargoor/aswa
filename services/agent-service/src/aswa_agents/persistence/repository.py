"""Repository classes for data access."""

from datetime import datetime, timezone
from typing import Any, Tuple
from uuid import UUID, uuid4

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


def utcnow():
    """Get current UTC time."""
    return datetime.now(timezone.utc)


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
                last_execution_at=utcnow(),
            )
        )
        await self.session.execute(stmt)


class DBExecutionRepository:
    """Database-backed repository for execution records."""

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
        agent_name: str | None = None,
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


class DBActionRepository:
    """Database-backed repository for action records."""

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
            reasoning=getattr(action, "reasoning", None),
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
            values["started_at"] = utcnow()

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
                external_id=getattr(result, "external_id", None),
                external_url=getattr(result, "external_url", None),
                error_message=result.error_message,
                error_code=getattr(result, "error_code", None),
                error_details=getattr(result, "error_details", None),
                retries_used=getattr(result, "retries_used", 0),
                completed_at=result.completed_at,
                duration_ms=getattr(result, "execution_time_ms", None),
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
                approved_at=utcnow(),
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
                approved_at=utcnow(),
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


# ============================================================================
# In-memory repositories for testing and development without a database
# ============================================================================

class ActionRepository:
    """In-memory repository for action persistence (for testing).

    For production, use DBActionRepository with a database session.
    """

    def __init__(self):
        self._actions: dict[UUID, dict[str, Any]] = {}

    async def save(
        self,
        action: Any,
        agent_name: str,
        context: Any,
    ) -> None:
        """Save an action record."""
        self._actions[action.id] = {
            "id": action.id,
            "type": action.type.value,
            "target_system": action.target_system,
            "parameters": action.parameters,
            "confidence": action.confidence,
            "status": ActionStatus.PENDING.value,
            "agent_name": agent_name,
            "action": action.model_dump() if hasattr(action, "model_dump") else {},
            "context": context.model_dump() if hasattr(context, "model_dump") else {},
            "created_at": utcnow(),
        }

    async def get(self, action_id: UUID) -> dict[str, Any] | None:
        """Get an action by ID."""
        return self._actions.get(action_id)

    async def update_status(self, action_id: UUID, status: ActionStatus) -> None:
        """Update action status."""
        if action_id in self._actions:
            self._actions[action_id]["status"] = status.value
            self._actions[action_id]["updated_at"] = utcnow()

    async def update_result(self, action_id: UUID, result: Any) -> None:
        """Update action with execution result."""
        if action_id in self._actions:
            self._actions[action_id]["result"] = (
                result.model_dump() if hasattr(result, "model_dump") else {}
            )
            self._actions[action_id]["status"] = result.status.value
            self._actions[action_id]["completed_at"] = utcnow()

    async def list_by_execution(self, execution_id: UUID) -> list[dict[str, Any]]:
        """List actions for an execution."""
        return [
            action
            for action in self._actions.values()
            if action.get("context", {}).get("execution_id") == str(execution_id)
        ]


class ExecutionRepository:
    """In-memory repository for execution persistence (for testing).

    For production, use DBExecutionRepository with a database session.
    """

    def __init__(self):
        self._executions: dict[UUID, Any] = {}

    async def save(self, execution: Any) -> None:
        """Save an execution record."""
        self._executions[execution.execution_id] = execution

    async def get(self, execution_id: UUID) -> Any | None:
        """Get an execution by ID."""
        return self._executions.get(execution_id)

    async def update(self, execution: Any) -> None:
        """Update an execution record."""
        self._executions[execution.execution_id] = execution

    async def list_by_tenant(
        self,
        tenant_id: str,
        agent_name: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[list[Any], int]:
        """List executions for a tenant."""
        filtered = [
            e
            for e in self._executions.values()
            if e.tenant_id == tenant_id
            and (agent_name is None or getattr(e, "agent_name", None) == agent_name)
            and (status is None or e.status.value == status)
        ]

        total = len(filtered)
        paginated = filtered[offset : offset + limit]
        return paginated, total

    async def delete(self, execution_id: UUID) -> bool:
        """Delete an execution."""
        if execution_id in self._executions:
            del self._executions[execution_id]
            return True
        return False
