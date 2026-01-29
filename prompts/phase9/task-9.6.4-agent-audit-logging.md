# Task 9.6.4: Agent Audit Logging

## Objective

Implement comprehensive audit logging for agent activities including execution traces, permission checks, approval decisions, and security events.

## Prerequisites

- Task 9.6.1-9.6.3 completed (Approval and Permissions)
- Logging infrastructure

## Implementation

### Step 1: Audit Models

```python
# services/agent-service/src/aswa_agents/models/audit.py
"""Audit logging models."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import Column, String, DateTime, JSON, Text, Index
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from aswa_agents.db.base import Base


class AuditEventType(str, Enum):
    """Types of audit events."""

    # Agent lifecycle
    AGENT_CREATED = "agent.created"
    AGENT_UPDATED = "agent.updated"
    AGENT_DELETED = "agent.deleted"
    AGENT_DEPLOYED = "agent.deployed"
    AGENT_SUSPENDED = "agent.suspended"

    # Execution events
    EXECUTION_STARTED = "execution.started"
    EXECUTION_COMPLETED = "execution.completed"
    EXECUTION_FAILED = "execution.failed"
    EXECUTION_CANCELLED = "execution.cancelled"
    EXECUTION_TIMEOUT = "execution.timeout"

    # Action events
    ACTION_STARTED = "action.started"
    ACTION_COMPLETED = "action.completed"
    ACTION_FAILED = "action.failed"
    ACTION_SKIPPED = "action.skipped"

    # Approval events
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_APPROVED = "approval.approved"
    APPROVAL_REJECTED = "approval.rejected"
    APPROVAL_EXPIRED = "approval.expired"

    # Permission events
    PERMISSION_GRANTED = "permission.granted"
    PERMISSION_REVOKED = "permission.revoked"
    PERMISSION_DENIED = "permission.denied"
    PERMISSION_CHECK = "permission.check"

    # Security events
    SECURITY_RATE_LIMITED = "security.rate_limited"
    SECURITY_BLOCKED = "security.blocked"
    SECURITY_ALERT = "security.alert"

    # Data access events
    DATA_ACCESSED = "data.accessed"
    DATA_MODIFIED = "data.modified"
    DATA_EXPORTED = "data.exported"

    # Configuration events
    CONFIG_CHANGED = "config.changed"
    POLICY_APPLIED = "policy.applied"
    RULE_TRIGGERED = "rule.triggered"


class AuditSeverity(str, Enum):
    """Audit event severity levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditLogModel(Base):
    """SQLAlchemy model for audit logs."""

    __tablename__ = "audit_logs"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(String(100), nullable=False)

    # Event identification
    event_type = Column(String(100), nullable=False)
    severity = Column(String(20), default=AuditSeverity.INFO.value)

    # Actor information
    actor_type = Column(String(50), nullable=False)  # user, agent, system
    actor_id = Column(String(200), nullable=True)
    actor_name = Column(String(200), nullable=True)

    # Target information
    target_type = Column(String(50), nullable=True)  # agent, execution, etc.
    target_id = Column(String(200), nullable=True)
    target_name = Column(String(200), nullable=True)

    # Event details
    message = Column(Text, nullable=False)
    details = Column(JSON, default=dict)

    # Context
    execution_id = Column(PGUUID(as_uuid=True), nullable=True)
    action_id = Column(String(100), nullable=True)
    request_id = Column(String(100), nullable=True)
    trace_id = Column(String(100), nullable=True)

    # Request metadata
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)

    # Result
    success = Column(String(10), default="true")  # true, false, partial
    error = Column(Text, nullable=True)

    # Timestamps
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_audit_logs_tenant_id", "tenant_id"),
        Index("idx_audit_logs_event_type", "event_type"),
        Index("idx_audit_logs_actor_id", "actor_id"),
        Index("idx_audit_logs_target_id", "target_id"),
        Index("idx_audit_logs_timestamp", "timestamp"),
        Index("idx_audit_logs_execution_id", "execution_id"),
        Index("idx_audit_logs_severity", "severity"),
    )


# Pydantic models
class AuditEvent(BaseModel):
    """Audit event for logging."""

    event_type: AuditEventType
    severity: AuditSeverity = AuditSeverity.INFO
    actor_type: str
    actor_id: str | None = None
    actor_name: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    target_name: str | None = None
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    execution_id: UUID | None = None
    action_id: str | None = None
    request_id: str | None = None
    trace_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    success: bool = True
    error: str | None = None


class AuditLogEntry(BaseModel):
    """Audit log entry response."""

    id: UUID
    event_type: str
    severity: str
    actor_type: str
    actor_id: str | None
    actor_name: str | None
    target_type: str | None
    target_id: str | None
    target_name: str | None
    message: str
    details: dict[str, Any]
    execution_id: UUID | None
    timestamp: datetime
    success: str


class AuditQuery(BaseModel):
    """Query parameters for audit logs."""

    event_types: list[str] | None = None
    actor_id: str | None = None
    target_id: str | None = None
    execution_id: UUID | None = None
    severity: list[str] | None = None
    since: datetime | None = None
    until: datetime | None = None
    limit: int = 100
    offset: int = 0
```

### Step 2: Audit Repository

```python
# services/agent-service/src/aswa_agents/repositories/audit_repository.py
"""Repository for audit logging."""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from aswa_agents.db.session import get_session
from aswa_agents.models.audit import (
    AuditLogModel,
    AuditEvent,
    AuditEventType,
    AuditSeverity,
    AuditQuery,
)

logger = structlog.get_logger()


class AuditRepository:
    """Repository for managing audit logs."""

    def __init__(self, session: AsyncSession | None = None):
        self._session = session
        self._logger = logger.bind(component="AuditRepository")

    async def _get_session(self) -> AsyncSession:
        if self._session:
            return self._session
        return await get_session()

    async def log(
        self,
        tenant_id: str,
        event: AuditEvent,
    ) -> AuditLogModel:
        """Log an audit event."""
        session = await self._get_session()

        log_entry = AuditLogModel(
            tenant_id=tenant_id,
            event_type=event.event_type.value,
            severity=event.severity.value,
            actor_type=event.actor_type,
            actor_id=event.actor_id,
            actor_name=event.actor_name,
            target_type=event.target_type,
            target_id=event.target_id,
            target_name=event.target_name,
            message=event.message,
            details=event.details,
            execution_id=event.execution_id,
            action_id=event.action_id,
            request_id=event.request_id,
            trace_id=event.trace_id,
            ip_address=event.ip_address,
            user_agent=event.user_agent,
            success="true" if event.success else "false",
            error=event.error,
        )

        session.add(log_entry)
        await session.commit()

        return log_entry

    async def query(
        self,
        tenant_id: str,
        query: AuditQuery,
    ) -> tuple[list[AuditLogModel], int]:
        """Query audit logs."""
        session = await self._get_session()

        conditions = [AuditLogModel.tenant_id == tenant_id]

        if query.event_types:
            conditions.append(AuditLogModel.event_type.in_(query.event_types))
        if query.actor_id:
            conditions.append(AuditLogModel.actor_id == query.actor_id)
        if query.target_id:
            conditions.append(AuditLogModel.target_id == query.target_id)
        if query.execution_id:
            conditions.append(AuditLogModel.execution_id == query.execution_id)
        if query.severity:
            conditions.append(AuditLogModel.severity.in_(query.severity))
        if query.since:
            conditions.append(AuditLogModel.timestamp >= query.since)
        if query.until:
            conditions.append(AuditLogModel.timestamp <= query.until)

        # Get total count
        count_result = await session.execute(
            select(func.count())
            .select_from(AuditLogModel)
            .where(and_(*conditions))
        )
        total = count_result.scalar()

        # Get logs
        result = await session.execute(
            select(AuditLogModel)
            .where(and_(*conditions))
            .order_by(desc(AuditLogModel.timestamp))
            .limit(query.limit)
            .offset(query.offset)
        )

        return result.scalars().all(), total

    async def get_by_execution(
        self,
        execution_id: UUID,
        tenant_id: str,
    ) -> list[AuditLogModel]:
        """Get all audit logs for an execution."""
        session = await self._get_session()

        result = await session.execute(
            select(AuditLogModel)
            .where(
                and_(
                    AuditLogModel.execution_id == execution_id,
                    AuditLogModel.tenant_id == tenant_id,
                )
            )
            .order_by(AuditLogModel.timestamp)
        )

        return result.scalars().all()

    async def get_by_agent(
        self,
        agent_id: str,
        tenant_id: str,
        limit: int = 100,
        event_types: list[str] | None = None,
    ) -> list[AuditLogModel]:
        """Get audit logs for an agent."""
        session = await self._get_session()

        conditions = [
            AuditLogModel.tenant_id == tenant_id,
            AuditLogModel.target_id == agent_id,
        ]

        if event_types:
            conditions.append(AuditLogModel.event_type.in_(event_types))

        result = await session.execute(
            select(AuditLogModel)
            .where(and_(*conditions))
            .order_by(desc(AuditLogModel.timestamp))
            .limit(limit)
        )

        return result.scalars().all()

    async def get_security_events(
        self,
        tenant_id: str,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditLogModel]:
        """Get security-related events."""
        session = await self._get_session()

        security_types = [
            AuditEventType.SECURITY_RATE_LIMITED.value,
            AuditEventType.SECURITY_BLOCKED.value,
            AuditEventType.SECURITY_ALERT.value,
            AuditEventType.PERMISSION_DENIED.value,
        ]

        conditions = [
            AuditLogModel.tenant_id == tenant_id,
            AuditLogModel.event_type.in_(security_types),
        ]

        if since:
            conditions.append(AuditLogModel.timestamp >= since)

        result = await session.execute(
            select(AuditLogModel)
            .where(and_(*conditions))
            .order_by(desc(AuditLogModel.timestamp))
            .limit(limit)
        )

        return result.scalars().all()

    async def get_stats(
        self,
        tenant_id: str,
        days: int = 7,
    ) -> dict[str, Any]:
        """Get audit log statistics."""
        session = await self._get_session()

        since = datetime.utcnow() - timedelta(days=days)

        # Events by type
        type_result = await session.execute(
            select(
                AuditLogModel.event_type,
                func.count(),
            )
            .where(
                and_(
                    AuditLogModel.tenant_id == tenant_id,
                    AuditLogModel.timestamp >= since,
                )
            )
            .group_by(AuditLogModel.event_type)
        )
        by_type = {row[0]: row[1] for row in type_result}

        # Events by severity
        severity_result = await session.execute(
            select(
                AuditLogModel.severity,
                func.count(),
            )
            .where(
                and_(
                    AuditLogModel.tenant_id == tenant_id,
                    AuditLogModel.timestamp >= since,
                )
            )
            .group_by(AuditLogModel.severity)
        )
        by_severity = {row[0]: row[1] for row in severity_result}

        # Failed events
        failed_result = await session.execute(
            select(func.count())
            .select_from(AuditLogModel)
            .where(
                and_(
                    AuditLogModel.tenant_id == tenant_id,
                    AuditLogModel.timestamp >= since,
                    AuditLogModel.success == "false",
                )
            )
        )
        failed_count = failed_result.scalar()

        # Total events
        total_result = await session.execute(
            select(func.count())
            .select_from(AuditLogModel)
            .where(
                and_(
                    AuditLogModel.tenant_id == tenant_id,
                    AuditLogModel.timestamp >= since,
                )
            )
        )
        total_count = total_result.scalar()

        return {
            "period_days": days,
            "total_events": total_count,
            "by_type": by_type,
            "by_severity": by_severity,
            "failed_events": failed_count,
            "failure_rate": failed_count / total_count if total_count > 0 else 0,
        }

    async def cleanup_old_logs(
        self,
        tenant_id: str,
        retention_days: int = 90,
    ) -> int:
        """Delete old audit logs."""
        session = await self._get_session()

        cutoff = datetime.utcnow() - timedelta(days=retention_days)

        result = await session.execute(
            AuditLogModel.__table__.delete().where(
                and_(
                    AuditLogModel.tenant_id == tenant_id,
                    AuditLogModel.timestamp < cutoff,
                )
            )
        )

        await session.commit()

        count = result.rowcount
        if count > 0:
            self._logger.info(
                "Cleaned up old audit logs",
                tenant_id=tenant_id,
                count=count,
            )

        return count
```

### Step 3: Audit Service

```python
# services/agent-service/src/aswa_agents/services/audit_service.py
"""Audit service for logging agent activities."""

from contextvars import ContextVar
from datetime import datetime
from typing import Any
from uuid import UUID

import structlog

from aswa_agents.models.audit import (
    AuditEvent,
    AuditEventType,
    AuditSeverity,
    AuditQuery,
)
from aswa_agents.repositories.audit_repository import AuditRepository

logger = structlog.get_logger()

# Context variables for request tracking
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)
_actor_id: ContextVar[str | None] = ContextVar("actor_id", default=None)
_actor_type: ContextVar[str] = ContextVar("actor_type", default="system")


def set_audit_context(
    request_id: str | None = None,
    trace_id: str | None = None,
    actor_id: str | None = None,
    actor_type: str = "system",
) -> None:
    """Set audit context for current request."""
    if request_id:
        _request_id.set(request_id)
    if trace_id:
        _trace_id.set(trace_id)
    if actor_id:
        _actor_id.set(actor_id)
    _actor_type.set(actor_type)


class AuditService:
    """
    Service for comprehensive audit logging.

    Provides logging for all agent activities with
    context tracking and security monitoring.
    """

    def __init__(self):
        self._repo = AuditRepository()
        self._logger = logger.bind(component="AuditService")

    async def log(
        self,
        tenant_id: str,
        event_type: AuditEventType,
        message: str,
        target_type: str | None = None,
        target_id: str | None = None,
        target_name: str | None = None,
        details: dict[str, Any] | None = None,
        execution_id: UUID | None = None,
        action_id: str | None = None,
        severity: AuditSeverity = AuditSeverity.INFO,
        success: bool = True,
        error: str | None = None,
        actor_id: str | None = None,
        actor_type: str | None = None,
        actor_name: str | None = None,
    ) -> None:
        """Log an audit event."""
        event = AuditEvent(
            event_type=event_type,
            severity=severity,
            actor_type=actor_type or _actor_type.get(),
            actor_id=actor_id or _actor_id.get(),
            actor_name=actor_name,
            target_type=target_type,
            target_id=target_id,
            target_name=target_name,
            message=message,
            details=details or {},
            execution_id=execution_id,
            action_id=action_id,
            request_id=_request_id.get(),
            trace_id=_trace_id.get(),
            success=success,
            error=error,
        )

        await self._repo.log(tenant_id, event)

        # Also log to structured logger
        log_method = {
            AuditSeverity.DEBUG: self._logger.debug,
            AuditSeverity.INFO: self._logger.info,
            AuditSeverity.WARNING: self._logger.warning,
            AuditSeverity.ERROR: self._logger.error,
            AuditSeverity.CRITICAL: self._logger.critical,
        }.get(severity, self._logger.info)

        log_method(
            message,
            event_type=event_type.value,
            target_id=target_id,
            execution_id=str(execution_id) if execution_id else None,
            success=success,
        )

    # Convenience methods for common events

    async def log_agent_created(
        self,
        tenant_id: str,
        agent_id: str,
        agent_name: str,
        created_by: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Log agent creation."""
        await self.log(
            tenant_id=tenant_id,
            event_type=AuditEventType.AGENT_CREATED,
            message=f"Agent '{agent_name}' created",
            target_type="agent",
            target_id=agent_id,
            target_name=agent_name,
            details=details,
            actor_id=created_by,
            actor_type="user",
        )

    async def log_execution_started(
        self,
        tenant_id: str,
        execution_id: UUID,
        agent_id: str,
        agent_name: str,
        trigger_type: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Log execution start."""
        await self.log(
            tenant_id=tenant_id,
            event_type=AuditEventType.EXECUTION_STARTED,
            message=f"Execution started for agent '{agent_name}'",
            target_type="agent",
            target_id=agent_id,
            target_name=agent_name,
            execution_id=execution_id,
            details={
                "trigger_type": trigger_type,
                **(details or {}),
            },
            actor_type="system",
        )

    async def log_execution_completed(
        self,
        tenant_id: str,
        execution_id: UUID,
        agent_id: str,
        duration_ms: int,
        actions_executed: int,
    ) -> None:
        """Log execution completion."""
        await self.log(
            tenant_id=tenant_id,
            event_type=AuditEventType.EXECUTION_COMPLETED,
            message=f"Execution completed in {duration_ms}ms",
            target_type="execution",
            target_id=str(execution_id),
            execution_id=execution_id,
            details={
                "agent_id": agent_id,
                "duration_ms": duration_ms,
                "actions_executed": actions_executed,
            },
            actor_type="agent",
            actor_id=agent_id,
        )

    async def log_execution_failed(
        self,
        tenant_id: str,
        execution_id: UUID,
        agent_id: str,
        error: str,
    ) -> None:
        """Log execution failure."""
        await self.log(
            tenant_id=tenant_id,
            event_type=AuditEventType.EXECUTION_FAILED,
            message="Execution failed",
            target_type="execution",
            target_id=str(execution_id),
            execution_id=execution_id,
            severity=AuditSeverity.ERROR,
            success=False,
            error=error,
            details={"agent_id": agent_id},
            actor_type="agent",
            actor_id=agent_id,
        )

    async def log_action_executed(
        self,
        tenant_id: str,
        execution_id: UUID,
        action_id: str,
        action_type: str,
        success: bool,
        duration_ms: int,
        error: str | None = None,
    ) -> None:
        """Log action execution."""
        event_type = (
            AuditEventType.ACTION_COMPLETED if success
            else AuditEventType.ACTION_FAILED
        )

        await self.log(
            tenant_id=tenant_id,
            event_type=event_type,
            message=f"Action '{action_id}' {'completed' if success else 'failed'}",
            target_type="action",
            target_id=action_id,
            execution_id=execution_id,
            action_id=action_id,
            severity=AuditSeverity.INFO if success else AuditSeverity.ERROR,
            success=success,
            error=error,
            details={
                "action_type": action_type,
                "duration_ms": duration_ms,
            },
        )

    async def log_approval_requested(
        self,
        tenant_id: str,
        approval_id: str,
        agent_id: str,
        action_id: str | None,
        title: str,
    ) -> None:
        """Log approval request."""
        await self.log(
            tenant_id=tenant_id,
            event_type=AuditEventType.APPROVAL_REQUESTED,
            message=f"Approval requested: {title}",
            target_type="approval",
            target_id=approval_id,
            details={
                "agent_id": agent_id,
                "action_id": action_id,
            },
            actor_type="agent",
            actor_id=agent_id,
        )

    async def log_approval_decision(
        self,
        tenant_id: str,
        approval_id: str,
        approved: bool,
        decided_by: str,
        notes: str | None = None,
    ) -> None:
        """Log approval decision."""
        event_type = (
            AuditEventType.APPROVAL_APPROVED if approved
            else AuditEventType.APPROVAL_REJECTED
        )

        await self.log(
            tenant_id=tenant_id,
            event_type=event_type,
            message=f"Approval {'approved' if approved else 'rejected'}",
            target_type="approval",
            target_id=approval_id,
            details={"notes": notes} if notes else {},
            actor_type="user",
            actor_id=decided_by,
            actor_name=decided_by,
        )

    async def log_permission_check(
        self,
        tenant_id: str,
        agent_id: str,
        permission: str,
        allowed: bool,
        reason: str | None = None,
    ) -> None:
        """Log permission check."""
        event_type = (
            AuditEventType.PERMISSION_CHECK if allowed
            else AuditEventType.PERMISSION_DENIED
        )

        await self.log(
            tenant_id=tenant_id,
            event_type=event_type,
            message=f"Permission {'granted' if allowed else 'denied'}: {permission}",
            target_type="agent",
            target_id=agent_id,
            severity=AuditSeverity.INFO if allowed else AuditSeverity.WARNING,
            success=allowed,
            details={
                "permission": permission,
                "reason": reason,
            },
        )

    async def log_security_event(
        self,
        tenant_id: str,
        event_type: AuditEventType,
        message: str,
        target_id: str | None = None,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> None:
        """Log security event."""
        await self.log(
            tenant_id=tenant_id,
            event_type=event_type,
            message=message,
            target_type="security",
            target_id=target_id,
            severity=AuditSeverity.WARNING,
            details=details,
        )

    # Query methods

    async def query_logs(
        self,
        tenant_id: str,
        query: AuditQuery,
    ) -> dict[str, Any]:
        """Query audit logs."""
        logs, total = await self._repo.query(tenant_id, query)

        return {
            "logs": [self._to_dict(log) for log in logs],
            "total": total,
            "limit": query.limit,
            "offset": query.offset,
        }

    async def get_execution_trace(
        self,
        tenant_id: str,
        execution_id: UUID,
    ) -> list[dict[str, Any]]:
        """Get full execution trace."""
        logs = await self._repo.get_by_execution(execution_id, tenant_id)
        return [self._to_dict(log) for log in logs]

    async def get_agent_activity(
        self,
        tenant_id: str,
        agent_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get agent activity log."""
        logs = await self._repo.get_by_agent(agent_id, tenant_id, limit)
        return [self._to_dict(log) for log in logs]

    async def get_security_events(
        self,
        tenant_id: str,
        since: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Get security events."""
        logs = await self._repo.get_security_events(tenant_id, since)
        return [self._to_dict(log) for log in logs]

    async def get_stats(
        self,
        tenant_id: str,
        days: int = 7,
    ) -> dict[str, Any]:
        """Get audit statistics."""
        return await self._repo.get_stats(tenant_id, days)

    def _to_dict(self, log) -> dict[str, Any]:
        """Convert log model to dict."""
        return {
            "id": str(log.id),
            "event_type": log.event_type,
            "severity": log.severity,
            "actor_type": log.actor_type,
            "actor_id": log.actor_id,
            "actor_name": log.actor_name,
            "target_type": log.target_type,
            "target_id": log.target_id,
            "target_name": log.target_name,
            "message": log.message,
            "details": log.details,
            "execution_id": str(log.execution_id) if log.execution_id else None,
            "action_id": log.action_id,
            "timestamp": log.timestamp.isoformat(),
            "success": log.success,
            "error": log.error,
        }


# Global instance for convenience
_audit_service: AuditService | None = None


def get_audit_service() -> AuditService:
    """Get the global audit service instance."""
    global _audit_service
    if _audit_service is None:
        _audit_service = AuditService()
    return _audit_service
```

### Step 4: Audit API Endpoints

```python
# services/agent-service/src/aswa_agents/api/audit.py
"""API endpoints for audit logs."""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from aswa_agents.models.audit import AuditQuery, AuditSeverity
from aswa_agents.services.audit_service import AuditService

router = APIRouter(prefix="/audit", tags=["audit"])


class AuditLogResponse(BaseModel):
    """Response for audit log queries."""

    logs: list[dict[str, Any]]
    total: int
    limit: int
    offset: int


class AuditStatsResponse(BaseModel):
    """Response for audit statistics."""

    period_days: int
    total_events: int
    by_type: dict[str, int]
    by_severity: dict[str, int]
    failed_events: int
    failure_rate: float


@router.get("", response_model=AuditLogResponse)
async def query_audit_logs(
    event_types: str | None = None,  # Comma-separated
    actor_id: str | None = None,
    target_id: str | None = None,
    execution_id: UUID | None = None,
    severity: str | None = None,  # Comma-separated
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> AuditLogResponse:
    """Query audit logs with filters."""
    tenant_id = "default-tenant"

    query = AuditQuery(
        event_types=event_types.split(",") if event_types else None,
        actor_id=actor_id,
        target_id=target_id,
        execution_id=execution_id,
        severity=severity.split(",") if severity else None,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )

    service = AuditService()
    result = await service.query_logs(tenant_id, query)

    return AuditLogResponse(**result)


@router.get("/stats", response_model=AuditStatsResponse)
async def get_audit_stats(
    days: int = Query(7, ge=1, le=90),
) -> AuditStatsResponse:
    """Get audit statistics."""
    tenant_id = "default-tenant"

    service = AuditService()
    stats = await service.get_stats(tenant_id, days)

    return AuditStatsResponse(**stats)


@router.get("/executions/{execution_id}")
async def get_execution_trace(execution_id: UUID) -> dict[str, Any]:
    """Get audit trail for an execution."""
    tenant_id = "default-tenant"

    service = AuditService()
    logs = await service.get_execution_trace(tenant_id, execution_id)

    return {
        "execution_id": str(execution_id),
        "events": logs,
        "count": len(logs),
    }


@router.get("/agents/{agent_id}")
async def get_agent_activity(
    agent_id: str,
    limit: int = Query(100, ge=1, le=1000),
) -> dict[str, Any]:
    """Get activity log for an agent."""
    tenant_id = "default-tenant"

    service = AuditService()
    logs = await service.get_agent_activity(tenant_id, agent_id, limit)

    return {
        "agent_id": agent_id,
        "events": logs,
        "count": len(logs),
    }


@router.get("/security")
async def get_security_events(
    since: datetime | None = None,
    limit: int = Query(100, ge=1, le=1000),
) -> dict[str, Any]:
    """Get security events."""
    tenant_id = "default-tenant"

    service = AuditService()
    logs = await service.get_security_events(tenant_id, since)

    return {
        "events": logs[:limit],
        "count": len(logs[:limit]),
    }


@router.get("/export")
async def export_audit_logs(
    since: datetime,
    until: datetime | None = None,
    format: str = "json",
) -> dict[str, Any]:
    """Export audit logs for compliance."""
    tenant_id = "default-tenant"

    query = AuditQuery(
        since=since,
        until=until or datetime.utcnow(),
        limit=10000,
    )

    service = AuditService()
    result = await service.query_logs(tenant_id, query)

    # Log the export
    await service.log(
        tenant_id=tenant_id,
        event_type=AuditEventType.DATA_EXPORTED,
        message=f"Audit logs exported ({result['total']} events)",
        details={"since": since.isoformat(), "format": format},
    )

    return result
```

### Step 5: Audit Middleware

```python
# services/agent-service/src/aswa_agents/middleware/audit.py
"""Audit middleware for request tracking."""

from uuid import uuid4
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from aswa_agents.services.audit_service import set_audit_context


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware to set audit context for each request."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Generate or get request ID
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        trace_id = request.headers.get("X-Trace-ID")

        # Get actor info from auth
        actor_id = None
        actor_type = "anonymous"

        if hasattr(request.state, "user"):
            actor_id = request.state.user.id
            actor_type = "user"
        elif request.headers.get("X-API-Key"):
            actor_type = "api_key"
            actor_id = request.headers.get("X-API-Key")[:8] + "..."

        # Set context
        set_audit_context(
            request_id=request_id,
            trace_id=trace_id,
            actor_id=actor_id,
            actor_type=actor_type,
        )

        # Add request ID to response
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        return response
```

## Test Cases

```python
# services/agent-service/tests/unit/test_audit.py
"""Tests for audit logging."""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, patch

from aswa_agents.models.audit import (
    AuditEvent,
    AuditEventType,
    AuditSeverity,
    AuditQuery,
)
from aswa_agents.services.audit_service import AuditService
from aswa_agents.repositories.audit_repository import AuditRepository


class TestAuditRepository:
    """Test AuditRepository."""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_log_event(self, mock_session):
        """Test logging an event."""
        repo = AuditRepository(session=mock_session)

        event = AuditEvent(
            event_type=AuditEventType.AGENT_CREATED,
            actor_type="user",
            actor_id="user123",
            message="Agent created",
        )

        await repo.log("test-tenant", event)

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_logs(self, mock_session):
        """Test querying logs."""
        repo = AuditRepository(session=mock_session)

        mock_log = AsyncMock()
        mock_session.execute.return_value = AsyncMock(
            scalar=lambda: 1,
            scalars=lambda: AsyncMock(all=lambda: [mock_log]),
        )

        query = AuditQuery(event_types=["agent.created"])

        with patch.object(mock_session, "execute") as mock_exec:
            mock_exec.return_value = AsyncMock(
                scalar=lambda: 1,
                scalars=lambda: AsyncMock(all=lambda: [mock_log]),
            )
            logs, total = await repo.query("test-tenant", query)

        # Query was executed
        assert mock_exec.called


class TestAuditService:
    """Test AuditService."""

    @pytest.fixture
    def service(self):
        return AuditService()

    @pytest.mark.asyncio
    async def test_log_agent_created(self, service):
        """Test logging agent creation."""
        with patch.object(service._repo, "log") as mock_log:
            await service.log_agent_created(
                tenant_id="test",
                agent_id="agent-123",
                agent_name="Test Agent",
                created_by="user@example.com",
            )

            mock_log.assert_called_once()
            event = mock_log.call_args[0][1]
            assert event.event_type == AuditEventType.AGENT_CREATED
            assert event.actor_id == "user@example.com"

    @pytest.mark.asyncio
    async def test_log_execution_started(self, service):
        """Test logging execution start."""
        with patch.object(service._repo, "log") as mock_log:
            execution_id = uuid4()
            await service.log_execution_started(
                tenant_id="test",
                execution_id=execution_id,
                agent_id="agent-123",
                agent_name="Test Agent",
                trigger_type="email",
            )

            mock_log.assert_called_once()
            event = mock_log.call_args[0][1]
            assert event.event_type == AuditEventType.EXECUTION_STARTED
            assert event.execution_id == execution_id

    @pytest.mark.asyncio
    async def test_log_execution_failed(self, service):
        """Test logging execution failure."""
        with patch.object(service._repo, "log") as mock_log:
            execution_id = uuid4()
            await service.log_execution_failed(
                tenant_id="test",
                execution_id=execution_id,
                agent_id="agent-123",
                error="Connection timeout",
            )

            mock_log.assert_called_once()
            event = mock_log.call_args[0][1]
            assert event.event_type == AuditEventType.EXECUTION_FAILED
            assert event.severity == AuditSeverity.ERROR
            assert event.success is False
            assert event.error == "Connection timeout"

    @pytest.mark.asyncio
    async def test_log_approval_decision(self, service):
        """Test logging approval decision."""
        with patch.object(service._repo, "log") as mock_log:
            await service.log_approval_decision(
                tenant_id="test",
                approval_id="approval-123",
                approved=True,
                decided_by="admin@example.com",
                notes="Looks good",
            )

            mock_log.assert_called_once()
            event = mock_log.call_args[0][1]
            assert event.event_type == AuditEventType.APPROVAL_APPROVED
            assert event.actor_type == "user"
            assert event.actor_id == "admin@example.com"

    @pytest.mark.asyncio
    async def test_log_permission_denied(self, service):
        """Test logging permission denial."""
        with patch.object(service._repo, "log") as mock_log:
            await service.log_permission_check(
                tenant_id="test",
                agent_id="agent-123",
                permission="action:send_email",
                allowed=False,
                reason="Permission not granted",
            )

            mock_log.assert_called_once()
            event = mock_log.call_args[0][1]
            assert event.event_type == AuditEventType.PERMISSION_DENIED
            assert event.severity == AuditSeverity.WARNING
            assert event.success is False

    @pytest.mark.asyncio
    async def test_get_execution_trace(self, service):
        """Test getting execution trace."""
        execution_id = uuid4()

        mock_log = AsyncMock()
        mock_log.id = uuid4()
        mock_log.event_type = AuditEventType.EXECUTION_STARTED.value
        mock_log.severity = AuditSeverity.INFO.value
        mock_log.actor_type = "system"
        mock_log.actor_id = None
        mock_log.actor_name = None
        mock_log.target_type = "agent"
        mock_log.target_id = "agent-123"
        mock_log.target_name = "Test Agent"
        mock_log.message = "Execution started"
        mock_log.details = {}
        mock_log.execution_id = execution_id
        mock_log.action_id = None
        mock_log.timestamp = datetime.utcnow()
        mock_log.success = "true"
        mock_log.error = None

        with patch.object(service._repo, "get_by_execution") as mock_get:
            mock_get.return_value = [mock_log]

            trace = await service.get_execution_trace("test", execution_id)

            assert len(trace) == 1
            assert trace[0]["event_type"] == AuditEventType.EXECUTION_STARTED.value


class TestAuditQuery:
    """Test audit query functionality."""

    @pytest.mark.asyncio
    async def test_query_by_event_type(self):
        """Test querying by event type."""
        service = AuditService()

        with patch.object(service._repo, "query") as mock_query:
            mock_query.return_value = ([], 0)

            query = AuditQuery(
                event_types=[AuditEventType.AGENT_CREATED.value],
                limit=50,
            )

            await service.query_logs("test", query)

            mock_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_by_date_range(self):
        """Test querying by date range."""
        service = AuditService()

        with patch.object(service._repo, "query") as mock_query:
            mock_query.return_value = ([], 0)

            query = AuditQuery(
                since=datetime.utcnow() - timedelta(days=7),
                until=datetime.utcnow(),
            )

            await service.query_logs("test", query)

            mock_query.assert_called_once()
```

## Verification Steps

1. **Run unit tests:**
   ```bash
   cd services/agent-service
   pytest tests/unit/test_audit.py -v
   ```

2. **Test audit logging:**
   ```python
   from aswa_agents.services.audit_service import AuditService
   from aswa_agents.models.audit import AuditEventType
   from uuid import uuid4

   service = AuditService()

   # Log agent creation
   await service.log_agent_created(
       tenant_id="test",
       agent_id="agent-123",
       agent_name="Email Agent",
       created_by="admin@example.com",
   )

   # Log execution
   execution_id = uuid4()
   await service.log_execution_started(
       tenant_id="test",
       execution_id=execution_id,
       agent_id="agent-123",
       agent_name="Email Agent",
       trigger_type="email",
   )
   ```

3. **Test API endpoints:**
   ```bash
   # Query audit logs
   curl "http://localhost:8000/api/v1/audit?event_types=agent.created,execution.started"

   # Get stats
   curl http://localhost:8000/api/v1/audit/stats?days=7

   # Get execution trace
   curl http://localhost:8000/api/v1/audit/executions/{execution_id}

   # Get agent activity
   curl http://localhost:8000/api/v1/audit/agents/{agent_id}

   # Get security events
   curl http://localhost:8000/api/v1/audit/security
   ```

## Next Task

Proceed to `task-9.7.1-agent-templates.md` for implementing agent templates.
