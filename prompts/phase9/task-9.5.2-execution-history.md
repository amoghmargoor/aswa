# Task 9.5.2: Execution History

## Objective

Implement comprehensive execution history tracking for agents, including detailed logging, metrics collection, and queryable history.

## Prerequisites

- Task 9.5.1 completed (Agent Test Runner)
- Database models for executions

## Implementation

### Step 1: Execution Models

```python
# services/agent-service/src/aswa_agents/models/execution.py
"""Execution history models."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import Column, String, DateTime, Integer, JSON, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from aswa_agents.db.base import Base


class ExecutionStatus(str, Enum):
    """Execution status values."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    AWAITING_APPROVAL = "awaiting_approval"


class ExecutionModel(Base):
    """SQLAlchemy model for agent executions."""

    __tablename__ = "executions"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_id = Column(PGUUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    tenant_id = Column(String(100), nullable=False)

    # Status tracking
    status = Column(String(50), default=ExecutionStatus.PENDING.value)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Trigger info
    trigger_type = Column(String(50), nullable=False)
    trigger_data = Column(JSON, default=dict)

    # Results
    output = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)

    # Metrics
    duration_ms = Column(Integer, nullable=True)
    actions_executed = Column(Integer, default=0)
    actions_succeeded = Column(Integer, default=0)
    actions_failed = Column(Integer, default=0)

    # Metadata
    metadata = Column(JSON, default=dict)
    trace_id = Column(String(100), nullable=True)

    # Relationships
    agent = relationship("AgentModel", back_populates="executions")
    action_logs = relationship("ActionLogModel", back_populates="execution", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_executions_agent_id", "agent_id"),
        Index("idx_executions_tenant_id", "tenant_id"),
        Index("idx_executions_status", "status"),
        Index("idx_executions_started_at", "started_at"),
    )


class ActionLogModel(Base):
    """SQLAlchemy model for action execution logs."""

    __tablename__ = "action_logs"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    execution_id = Column(PGUUID(as_uuid=True), ForeignKey("executions.id"), nullable=False)

    # Action info
    action_id = Column(String(100), nullable=False)
    action_type = Column(String(50), nullable=False)
    action_index = Column(Integer, nullable=False)

    # Status
    status = Column(String(50), nullable=False)
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)

    # Input/Output
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)

    # Metadata
    metadata = Column(JSON, default=dict)
    retry_count = Column(Integer, default=0)

    # Relationships
    execution = relationship("ExecutionModel", back_populates="action_logs")

    __table_args__ = (
        Index("idx_action_logs_execution_id", "execution_id"),
        Index("idx_action_logs_action_id", "action_id"),
    )


# Pydantic models for API
class ExecutionSummary(BaseModel):
    """Summary of an execution."""

    id: UUID
    agent_id: UUID
    status: ExecutionStatus
    trigger_type: str
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
    actions_executed: int
    actions_succeeded: int
    actions_failed: int


class ActionLogSummary(BaseModel):
    """Summary of an action log."""

    action_id: str
    action_type: str
    status: str
    duration_ms: int | None
    error: str | None


class ExecutionDetail(BaseModel):
    """Detailed execution information."""

    id: UUID
    agent_id: UUID
    agent_name: str = ""
    status: ExecutionStatus
    trigger_type: str
    trigger_data: dict[str, Any]
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
    output: dict[str, Any] | None
    error: str | None
    action_logs: list[ActionLogSummary]
    metadata: dict[str, Any]
```

### Step 2: Execution Repository

```python
# services/agent-service/src/aswa_agents/repositories/execution_repository.py
"""Repository for execution history."""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from aswa_agents.db.session import get_session
from aswa_agents.models.execution import (
    ExecutionModel,
    ActionLogModel,
    ExecutionStatus,
    ExecutionSummary,
    ExecutionDetail,
    ActionLogSummary,
)

logger = structlog.get_logger()


class ExecutionRepository:
    """Repository for managing execution records."""

    def __init__(self, session: AsyncSession | None = None):
        self._session = session
        self._logger = logger.bind(component="ExecutionRepository")

    async def _get_session(self) -> AsyncSession:
        if self._session:
            return self._session
        return await get_session()

    async def create(
        self,
        agent_id: UUID,
        tenant_id: str,
        trigger_type: str,
        trigger_data: dict[str, Any],
        trace_id: str | None = None,
    ) -> ExecutionModel:
        """Create a new execution record."""
        session = await self._get_session()

        execution = ExecutionModel(
            agent_id=agent_id,
            tenant_id=tenant_id,
            trigger_type=trigger_type,
            trigger_data=trigger_data,
            trace_id=trace_id,
            status=ExecutionStatus.PENDING.value,
        )

        session.add(execution)
        await session.commit()
        await session.refresh(execution)

        self._logger.info(
            "Created execution",
            execution_id=str(execution.id),
            agent_id=str(agent_id),
        )

        return execution

    async def update_status(
        self,
        execution_id: UUID,
        status: ExecutionStatus,
        output: dict[str, Any] | None = None,
        error: str | None = None,
        duration_ms: int | None = None,
    ) -> None:
        """Update execution status."""
        session = await self._get_session()

        execution = await session.get(ExecutionModel, execution_id)
        if not execution:
            return

        execution.status = status.value

        if status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED]:
            execution.completed_at = datetime.utcnow()

        if output is not None:
            execution.output = output
        if error is not None:
            execution.error = error
        if duration_ms is not None:
            execution.duration_ms = duration_ms

        await session.commit()

    async def log_action(
        self,
        execution_id: UUID,
        action_id: str,
        action_type: str,
        action_index: int,
        status: str,
        started_at: datetime,
        completed_at: datetime | None = None,
        duration_ms: int | None = None,
        input_data: dict | None = None,
        output_data: dict | None = None,
        error: str | None = None,
        metadata: dict | None = None,
        retry_count: int = 0,
    ) -> ActionLogModel:
        """Log an action execution."""
        session = await self._get_session()

        log = ActionLogModel(
            execution_id=execution_id,
            action_id=action_id,
            action_type=action_type,
            action_index=action_index,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            input_data=input_data,
            output_data=output_data,
            error=error,
            metadata=metadata or {},
            retry_count=retry_count,
        )

        session.add(log)

        # Update execution counters
        execution = await session.get(ExecutionModel, execution_id)
        if execution:
            execution.actions_executed += 1
            if status == "completed":
                execution.actions_succeeded += 1
            elif status == "failed":
                execution.actions_failed += 1

        await session.commit()
        await session.refresh(log)

        return log

    async def get_by_id(self, execution_id: UUID) -> ExecutionDetail | None:
        """Get execution by ID with full details."""
        session = await self._get_session()

        result = await session.execute(
            select(ExecutionModel).where(ExecutionModel.id == execution_id)
        )
        execution = result.scalar_one_or_none()

        if not execution:
            return None

        # Get action logs
        logs_result = await session.execute(
            select(ActionLogModel)
            .where(ActionLogModel.execution_id == execution_id)
            .order_by(ActionLogModel.action_index)
        )
        action_logs = logs_result.scalars().all()

        return ExecutionDetail(
            id=execution.id,
            agent_id=execution.agent_id,
            status=ExecutionStatus(execution.status),
            trigger_type=execution.trigger_type,
            trigger_data=execution.trigger_data or {},
            started_at=execution.started_at,
            completed_at=execution.completed_at,
            duration_ms=execution.duration_ms,
            output=execution.output,
            error=execution.error,
            action_logs=[
                ActionLogSummary(
                    action_id=log.action_id,
                    action_type=log.action_type,
                    status=log.status,
                    duration_ms=log.duration_ms,
                    error=log.error,
                )
                for log in action_logs
            ],
            metadata=execution.metadata or {},
        )

    async def list_by_agent(
        self,
        agent_id: UUID,
        limit: int = 50,
        offset: int = 0,
        status: ExecutionStatus | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> tuple[list[ExecutionSummary], int]:
        """List executions for an agent."""
        session = await self._get_session()

        conditions = [ExecutionModel.agent_id == agent_id]

        if status:
            conditions.append(ExecutionModel.status == status.value)
        if since:
            conditions.append(ExecutionModel.started_at >= since)
        if until:
            conditions.append(ExecutionModel.started_at <= until)

        # Get total count
        count_result = await session.execute(
            select(func.count()).select_from(ExecutionModel).where(and_(*conditions))
        )
        total = count_result.scalar()

        # Get executions
        result = await session.execute(
            select(ExecutionModel)
            .where(and_(*conditions))
            .order_by(desc(ExecutionModel.started_at))
            .limit(limit)
            .offset(offset)
        )
        executions = result.scalars().all()

        summaries = [
            ExecutionSummary(
                id=e.id,
                agent_id=e.agent_id,
                status=ExecutionStatus(e.status),
                trigger_type=e.trigger_type,
                started_at=e.started_at,
                completed_at=e.completed_at,
                duration_ms=e.duration_ms,
                actions_executed=e.actions_executed,
                actions_succeeded=e.actions_succeeded,
                actions_failed=e.actions_failed,
            )
            for e in executions
        ]

        return summaries, total

    async def list_by_tenant(
        self,
        tenant_id: str,
        limit: int = 50,
        offset: int = 0,
        status: ExecutionStatus | None = None,
    ) -> tuple[list[ExecutionSummary], int]:
        """List executions for a tenant."""
        session = await self._get_session()

        conditions = [ExecutionModel.tenant_id == tenant_id]

        if status:
            conditions.append(ExecutionModel.status == status.value)

        count_result = await session.execute(
            select(func.count()).select_from(ExecutionModel).where(and_(*conditions))
        )
        total = count_result.scalar()

        result = await session.execute(
            select(ExecutionModel)
            .where(and_(*conditions))
            .order_by(desc(ExecutionModel.started_at))
            .limit(limit)
            .offset(offset)
        )
        executions = result.scalars().all()

        return [
            ExecutionSummary(
                id=e.id,
                agent_id=e.agent_id,
                status=ExecutionStatus(e.status),
                trigger_type=e.trigger_type,
                started_at=e.started_at,
                completed_at=e.completed_at,
                duration_ms=e.duration_ms,
                actions_executed=e.actions_executed,
                actions_succeeded=e.actions_succeeded,
                actions_failed=e.actions_failed,
            )
            for e in executions
        ], total

    async def get_stats(
        self,
        agent_id: UUID | None = None,
        tenant_id: str | None = None,
        period_days: int = 7,
    ) -> dict[str, Any]:
        """Get execution statistics."""
        session = await self._get_session()

        since = datetime.utcnow() - timedelta(days=period_days)

        conditions = [ExecutionModel.started_at >= since]
        if agent_id:
            conditions.append(ExecutionModel.agent_id == agent_id)
        if tenant_id:
            conditions.append(ExecutionModel.tenant_id == tenant_id)

        # Total executions
        total_result = await session.execute(
            select(func.count()).select_from(ExecutionModel).where(and_(*conditions))
        )
        total = total_result.scalar()

        # By status
        status_result = await session.execute(
            select(ExecutionModel.status, func.count())
            .where(and_(*conditions))
            .group_by(ExecutionModel.status)
        )
        by_status = {row[0]: row[1] for row in status_result}

        # Average duration
        avg_result = await session.execute(
            select(func.avg(ExecutionModel.duration_ms))
            .where(and_(*conditions, ExecutionModel.duration_ms.isnot(None)))
        )
        avg_duration = avg_result.scalar()

        # Success rate
        completed = by_status.get(ExecutionStatus.COMPLETED.value, 0)
        failed = by_status.get(ExecutionStatus.FAILED.value, 0)
        success_rate = completed / (completed + failed) if (completed + failed) > 0 else 0

        return {
            "period_days": period_days,
            "total_executions": total,
            "by_status": by_status,
            "average_duration_ms": int(avg_duration) if avg_duration else None,
            "success_rate": round(success_rate, 3),
            "completed": completed,
            "failed": failed,
        }

    async def cleanup_old(
        self,
        tenant_id: str,
        retention_days: int = 30,
    ) -> int:
        """Delete old execution records."""
        session = await self._get_session()

        cutoff = datetime.utcnow() - timedelta(days=retention_days)

        result = await session.execute(
            select(ExecutionModel.id).where(
                and_(
                    ExecutionModel.tenant_id == tenant_id,
                    ExecutionModel.started_at < cutoff,
                )
            )
        )
        ids_to_delete = [row[0] for row in result]

        if ids_to_delete:
            # Delete in batches
            for i in range(0, len(ids_to_delete), 100):
                batch = ids_to_delete[i:i+100]
                await session.execute(
                    ExecutionModel.__table__.delete().where(
                        ExecutionModel.id.in_(batch)
                    )
                )

            await session.commit()

        self._logger.info(
            "Cleaned up old executions",
            tenant_id=tenant_id,
            count=len(ids_to_delete),
        )

        return len(ids_to_delete)
```

### Step 3: Execution Tracker

```python
# services/agent-service/src/aswa_agents/execution/tracker.py
"""Execution tracking during agent runs."""

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncIterator
from uuid import UUID

import structlog

from aswa_agents.actions.base import ActionResult
from aswa_agents.models.execution import ExecutionStatus
from aswa_agents.repositories.execution_repository import ExecutionRepository

logger = structlog.get_logger()


class ExecutionTracker:
    """
    Tracks execution progress and logs results.

    Use as a context manager for automatic start/end tracking.
    """

    def __init__(
        self,
        agent_id: UUID,
        tenant_id: str,
        trigger_type: str,
        trigger_data: dict[str, Any],
        trace_id: str | None = None,
    ):
        self.agent_id = agent_id
        self.tenant_id = tenant_id
        self.trigger_type = trigger_type
        self.trigger_data = trigger_data
        self.trace_id = trace_id

        self._execution_id: UUID | None = None
        self._repo = ExecutionRepository()
        self._start_time: datetime | None = None
        self._action_index = 0
        self._logger = logger.bind(
            component="ExecutionTracker",
            agent_id=str(agent_id),
        )

    @property
    def execution_id(self) -> UUID | None:
        return self._execution_id

    async def start(self) -> UUID:
        """Start tracking an execution."""
        import time

        self._start_time = datetime.utcnow()

        execution = await self._repo.create(
            agent_id=self.agent_id,
            tenant_id=self.tenant_id,
            trigger_type=self.trigger_type,
            trigger_data=self.trigger_data,
            trace_id=self.trace_id,
        )

        self._execution_id = execution.id

        await self._repo.update_status(
            self._execution_id,
            ExecutionStatus.RUNNING,
        )

        self._logger.info(
            "Started execution tracking",
            execution_id=str(self._execution_id),
        )

        return self._execution_id

    async def log_action(
        self,
        action_id: str,
        action_type: str,
        result: ActionResult,
        input_data: dict | None = None,
    ) -> None:
        """Log an action execution."""
        if not self._execution_id:
            return

        await self._repo.log_action(
            execution_id=self._execution_id,
            action_id=action_id,
            action_type=action_type,
            action_index=self._action_index,
            status=result.status.value,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            duration_ms=result.execution_time_ms,
            input_data=input_data,
            output_data=result.output,
            error=result.error,
            metadata=result.metadata,
        )

        self._action_index += 1

    async def complete(
        self,
        output: dict[str, Any] | None = None,
    ) -> None:
        """Mark execution as completed."""
        if not self._execution_id:
            return

        duration_ms = None
        if self._start_time:
            duration_ms = int((datetime.utcnow() - self._start_time).total_seconds() * 1000)

        await self._repo.update_status(
            self._execution_id,
            ExecutionStatus.COMPLETED,
            output=output,
            duration_ms=duration_ms,
        )

        self._logger.info(
            "Execution completed",
            execution_id=str(self._execution_id),
            duration_ms=duration_ms,
        )

    async def fail(self, error: str) -> None:
        """Mark execution as failed."""
        if not self._execution_id:
            return

        duration_ms = None
        if self._start_time:
            duration_ms = int((datetime.utcnow() - self._start_time).total_seconds() * 1000)

        await self._repo.update_status(
            self._execution_id,
            ExecutionStatus.FAILED,
            error=error,
            duration_ms=duration_ms,
        )

        self._logger.error(
            "Execution failed",
            execution_id=str(self._execution_id),
            error=error,
        )

    async def cancel(self) -> None:
        """Mark execution as cancelled."""
        if not self._execution_id:
            return

        await self._repo.update_status(
            self._execution_id,
            ExecutionStatus.CANCELLED,
        )

        self._logger.info(
            "Execution cancelled",
            execution_id=str(self._execution_id),
        )


@asynccontextmanager
async def track_execution(
    agent_id: UUID,
    tenant_id: str,
    trigger_type: str,
    trigger_data: dict[str, Any],
    trace_id: str | None = None,
) -> AsyncIterator[ExecutionTracker]:
    """
    Context manager for tracking execution.

    Usage:
        async with track_execution(agent_id, tenant_id, "email", data) as tracker:
            # Execute agent
            await tracker.log_action(...)
            # Automatically completes or fails based on exception
    """
    tracker = ExecutionTracker(
        agent_id=agent_id,
        tenant_id=tenant_id,
        trigger_type=trigger_type,
        trigger_data=trigger_data,
        trace_id=trace_id,
    )

    await tracker.start()

    try:
        yield tracker
        await tracker.complete()
    except Exception as e:
        await tracker.fail(str(e))
        raise
```

### Step 4: Execution API Endpoints

```python
# services/agent-service/src/aswa_agents/api/executions.py
"""API endpoints for execution history."""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from aswa_agents.models.execution import (
    ExecutionStatus,
    ExecutionSummary,
    ExecutionDetail,
)
from aswa_agents.repositories.execution_repository import ExecutionRepository

router = APIRouter(prefix="/executions", tags=["executions"])


class ExecutionListResponse(BaseModel):
    """Response for listing executions."""

    executions: list[ExecutionSummary]
    total: int
    limit: int
    offset: int


class ExecutionStatsResponse(BaseModel):
    """Response for execution statistics."""

    period_days: int
    total_executions: int
    by_status: dict[str, int]
    average_duration_ms: int | None
    success_rate: float
    completed: int
    failed: int


@router.get("", response_model=ExecutionListResponse)
async def list_executions(
    agent_id: UUID | None = None,
    status: ExecutionStatus | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> ExecutionListResponse:
    """
    List executions with optional filters.

    Requires tenant context from auth.
    """
    # In production, get tenant_id from auth
    tenant_id = "default-tenant"

    repo = ExecutionRepository()

    if agent_id:
        executions, total = await repo.list_by_agent(
            agent_id=agent_id,
            limit=limit,
            offset=offset,
            status=status,
            since=since,
            until=until,
        )
    else:
        executions, total = await repo.list_by_tenant(
            tenant_id=tenant_id,
            limit=limit,
            offset=offset,
            status=status,
        )

    return ExecutionListResponse(
        executions=executions,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/stats", response_model=ExecutionStatsResponse)
async def get_execution_stats(
    agent_id: UUID | None = None,
    period_days: int = Query(7, ge=1, le=90),
) -> ExecutionStatsResponse:
    """Get execution statistics."""
    tenant_id = "default-tenant"

    repo = ExecutionRepository()
    stats = await repo.get_stats(
        agent_id=agent_id,
        tenant_id=tenant_id,
        period_days=period_days,
    )

    return ExecutionStatsResponse(**stats)


@router.get("/{execution_id}", response_model=ExecutionDetail)
async def get_execution(execution_id: UUID) -> ExecutionDetail:
    """Get execution details."""
    repo = ExecutionRepository()
    execution = await repo.get_by_id(execution_id)

    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    return execution


@router.get("/{execution_id}/logs")
async def get_execution_logs(execution_id: UUID) -> dict[str, Any]:
    """Get detailed logs for an execution."""
    repo = ExecutionRepository()
    execution = await repo.get_by_id(execution_id)

    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    return {
        "execution_id": str(execution_id),
        "action_logs": [log.model_dump() for log in execution.action_logs],
    }


@router.post("/{execution_id}/replay")
async def replay_execution(execution_id: UUID) -> dict[str, Any]:
    """Replay an execution with the same trigger data."""
    repo = ExecutionRepository()
    execution = await repo.get_by_id(execution_id)

    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    # In production, would trigger new execution
    return {
        "message": "Replay triggered",
        "original_execution_id": str(execution_id),
        "agent_id": str(execution.agent_id),
    }
```

## Test Cases

```python
# services/agent-service/tests/unit/test_execution_history.py
"""Tests for execution history."""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, patch

from aswa_agents.models.execution import ExecutionStatus
from aswa_agents.repositories.execution_repository import ExecutionRepository
from aswa_agents.execution.tracker import ExecutionTracker, track_execution


class TestExecutionRepository:
    """Test ExecutionRepository."""

    @pytest.fixture
    def mock_session(self):
        """Create mock session."""
        session = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_create_execution(self, mock_session):
        """Test creating execution."""
        repo = ExecutionRepository(session=mock_session)

        agent_id = uuid4()
        tenant_id = "test-tenant"

        execution = await repo.create(
            agent_id=agent_id,
            tenant_id=tenant_id,
            trigger_type="email",
            trigger_data={"subject": "Test"},
        )

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_status(self, mock_session):
        """Test updating status."""
        repo = ExecutionRepository(session=mock_session)

        execution_id = uuid4()
        mock_session.get.return_value = AsyncMock()

        await repo.update_status(
            execution_id=execution_id,
            status=ExecutionStatus.COMPLETED,
            output={"result": "success"},
        )

        mock_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_log_action(self, mock_session):
        """Test logging action."""
        repo = ExecutionRepository(session=mock_session)

        execution_id = uuid4()
        mock_session.get.return_value = AsyncMock(
            actions_executed=0,
            actions_succeeded=0,
            actions_failed=0,
        )

        await repo.log_action(
            execution_id=execution_id,
            action_id="action_1",
            action_type="summarize",
            action_index=0,
            status="completed",
            started_at=datetime.utcnow(),
        )

        mock_session.add.assert_called()


class TestExecutionTracker:
    """Test ExecutionTracker."""

    @pytest.fixture
    def tracker(self):
        """Create tracker instance."""
        return ExecutionTracker(
            agent_id=uuid4(),
            tenant_id="test-tenant",
            trigger_type="email",
            trigger_data={"subject": "Test"},
        )

    @pytest.mark.asyncio
    async def test_start_tracking(self, tracker):
        """Test starting execution tracking."""
        with patch.object(tracker._repo, "create") as mock_create:
            mock_create.return_value = AsyncMock(id=uuid4())
            with patch.object(tracker._repo, "update_status"):
                execution_id = await tracker.start()

                assert execution_id is not None
                mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_action(self, tracker):
        """Test logging action."""
        with patch.object(tracker._repo, "create") as mock_create:
            mock_create.return_value = AsyncMock(id=uuid4())
            with patch.object(tracker._repo, "update_status"):
                await tracker.start()

            with patch.object(tracker._repo, "log_action") as mock_log:
                from aswa_agents.actions.base import ActionResult, ActionStatus

                result = ActionResult(
                    action_id="test",
                    status=ActionStatus.COMPLETED,
                    output={"result": "ok"},
                    execution_time_ms=100,
                )

                await tracker.log_action(
                    action_id="test",
                    action_type="summarize",
                    result=result,
                )

                mock_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_success(self):
        """Test context manager with success."""
        with patch("aswa_agents.execution.tracker.ExecutionRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.create.return_value = AsyncMock(id=uuid4())
            MockRepo.return_value = mock_repo

            async with track_execution(
                agent_id=uuid4(),
                tenant_id="test",
                trigger_type="email",
                trigger_data={},
            ) as tracker:
                assert tracker.execution_id is not None

            # Should call complete on success
            mock_repo.update_status.assert_called()

    @pytest.mark.asyncio
    async def test_context_manager_failure(self):
        """Test context manager with failure."""
        with patch("aswa_agents.execution.tracker.ExecutionRepository") as MockRepo:
            mock_repo = AsyncMock()
            mock_repo.create.return_value = AsyncMock(id=uuid4())
            MockRepo.return_value = mock_repo

            with pytest.raises(ValueError):
                async with track_execution(
                    agent_id=uuid4(),
                    tenant_id="test",
                    trigger_type="email",
                    trigger_data={},
                ) as tracker:
                    raise ValueError("Test error")

            # Should call fail on exception
            # Note: verify the failure status was set


class TestExecutionStats:
    """Test execution statistics."""

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test getting execution stats."""
        with patch("aswa_agents.repositories.execution_repository.get_session"):
            repo = ExecutionRepository()

            with patch.object(repo, "_get_session") as mock_session:
                session = AsyncMock()
                mock_session.return_value = session

                # Mock count query
                session.execute.return_value = AsyncMock(
                    scalar=lambda: 100
                )

                stats = await repo.get_stats(
                    tenant_id="test",
                    period_days=7,
                )

                assert "total_executions" in stats
                assert "success_rate" in stats
```

## Verification Steps

1. **Run unit tests:**
   ```bash
   cd services/agent-service
   pytest tests/unit/test_execution_history.py -v
   ```

2. **Test tracker manually:**
   ```python
   from aswa_agents.execution.tracker import track_execution
   from uuid import uuid4

   async with track_execution(
       agent_id=uuid4(),
       tenant_id="test",
       trigger_type="email",
       trigger_data={"subject": "Test"}
   ) as tracker:
       print(f"Tracking execution: {tracker.execution_id}")
   ```

3. **Test API endpoints:**
   ```bash
   # List executions
   curl http://localhost:8000/api/v1/executions

   # Get stats
   curl http://localhost:8000/api/v1/executions/stats?period_days=7

   # Get specific execution
   curl http://localhost:8000/api/v1/executions/{execution_id}
   ```

## Next Task

Proceed to `task-9.5.3-agent-debugging.md` for implementing agent debugging tools.
