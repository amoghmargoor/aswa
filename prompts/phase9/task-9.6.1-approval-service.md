# Task 9.6.1: Approval Service

## Objective

Implement the approval service for human-in-the-loop workflows, enabling agents to request and await human approval before executing sensitive actions.

## Prerequisites

- Task 9.5.x completed (Testing and Debugging)
- Database models for approvals

## Implementation

### Step 1: Approval Models

```python
# services/agent-service/src/aswa_agents/models/approval.py
"""Approval workflow models."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import Column, String, DateTime, Integer, JSON, Text, ForeignKey, Index, Boolean
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from aswa_agents.db.base import Base


class ApprovalStatus(str, Enum):
    """Approval request status."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ApprovalPriority(str, Enum):
    """Approval priority levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class ApprovalType(str, Enum):
    """Types of approval requests."""

    ACTION = "action"  # Single action approval
    EXECUTION = "execution"  # Full execution approval
    ESCALATION = "escalation"  # Escalated from automated decision
    SENSITIVE = "sensitive"  # Sensitive data access


class ApprovalRequestModel(Base):
    """SQLAlchemy model for approval requests."""

    __tablename__ = "approval_requests"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(String(100), nullable=False)

    # Request context
    agent_id = Column(PGUUID(as_uuid=True), ForeignKey("agents.id"), nullable=False)
    execution_id = Column(PGUUID(as_uuid=True), ForeignKey("executions.id"), nullable=True)
    action_id = Column(String(100), nullable=True)

    # Approval details
    approval_type = Column(String(50), default=ApprovalType.ACTION.value)
    status = Column(String(50), default=ApprovalStatus.PENDING.value)
    priority = Column(String(20), default=ApprovalPriority.MEDIUM.value)

    # Request content
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    action_summary = Column(Text, nullable=True)
    context_data = Column(JSON, default=dict)

    # Approval metadata
    requested_by = Column(String(100), nullable=True)  # User or system
    assigned_to = Column(String(100), nullable=True)  # Specific approver
    approved_by = Column(String(100), nullable=True)

    # Timing
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    responded_at = Column(DateTime, nullable=True)

    # Response
    response_notes = Column(Text, nullable=True)
    modifications = Column(JSON, nullable=True)  # Allowed modifications

    # Notification tracking
    notification_sent = Column(Boolean, default=False)
    reminder_count = Column(Integer, default=0)

    # Relationships
    agent = relationship("AgentModel", back_populates="approval_requests")

    __table_args__ = (
        Index("idx_approval_requests_tenant_id", "tenant_id"),
        Index("idx_approval_requests_status", "status"),
        Index("idx_approval_requests_agent_id", "agent_id"),
        Index("idx_approval_requests_assigned_to", "assigned_to"),
        Index("idx_approval_requests_created_at", "created_at"),
    )


class ApprovalRuleModel(Base):
    """SQLAlchemy model for approval rules."""

    __tablename__ = "approval_rules"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(String(100), nullable=False)

    # Rule identification
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    enabled = Column(Boolean, default=True)
    priority = Column(Integer, default=100)  # Lower = higher priority

    # Matching criteria
    agent_pattern = Column(String(200), nullable=True)  # Regex for agent names
    action_types = Column(JSON, default=list)  # Action types requiring approval
    trigger_types = Column(JSON, default=list)  # Trigger types

    # Conditions
    conditions = Column(JSON, default=dict)  # Field-based conditions

    # Approval settings
    approval_type = Column(String(50), default="review")  # auto, notify, review, manual
    required_approvers = Column(Integer, default=1)
    approver_roles = Column(JSON, default=list)
    timeout_hours = Column(Integer, default=24)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_approval_rules_tenant_id", "tenant_id"),
        Index("idx_approval_rules_enabled", "enabled"),
    )


# Pydantic models for API
class ApprovalRequestCreate(BaseModel):
    """Request to create an approval."""

    agent_id: UUID
    execution_id: UUID | None = None
    action_id: str | None = None
    approval_type: ApprovalType = ApprovalType.ACTION
    priority: ApprovalPriority = ApprovalPriority.MEDIUM
    title: str
    description: str | None = None
    action_summary: str | None = None
    context_data: dict[str, Any] = Field(default_factory=dict)
    assigned_to: str | None = None
    expires_in_hours: int = 24


class ApprovalRequestResponse(BaseModel):
    """Approval request response."""

    id: UUID
    agent_id: UUID
    execution_id: UUID | None
    action_id: str | None
    approval_type: ApprovalType
    status: ApprovalStatus
    priority: ApprovalPriority
    title: str
    description: str | None
    action_summary: str | None
    context_data: dict[str, Any]
    assigned_to: str | None
    created_at: datetime
    expires_at: datetime | None


class ApprovalDecision(BaseModel):
    """Approval decision input."""

    approved: bool
    notes: str | None = None
    modifications: dict[str, Any] | None = None


class ApprovalRuleCreate(BaseModel):
    """Request to create an approval rule."""

    name: str
    description: str | None = None
    enabled: bool = True
    priority: int = 100
    agent_pattern: str | None = None
    action_types: list[str] = Field(default_factory=list)
    trigger_types: list[str] = Field(default_factory=list)
    conditions: dict[str, Any] = Field(default_factory=dict)
    approval_type: str = "review"
    required_approvers: int = 1
    approver_roles: list[str] = Field(default_factory=list)
    timeout_hours: int = 24
```

### Step 2: Approval Repository

```python
# services/agent-service/src/aswa_agents/repositories/approval_repository.py
"""Repository for approval management."""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select, func, and_, or_, desc, update
from sqlalchemy.ext.asyncio import AsyncSession

from aswa_agents.db.session import get_session
from aswa_agents.models.approval import (
    ApprovalRequestModel,
    ApprovalRuleModel,
    ApprovalStatus,
    ApprovalPriority,
    ApprovalRequestCreate,
    ApprovalRequestResponse,
    ApprovalRuleCreate,
)

logger = structlog.get_logger()


class ApprovalRepository:
    """Repository for managing approval requests and rules."""

    def __init__(self, session: AsyncSession | None = None):
        self._session = session
        self._logger = logger.bind(component="ApprovalRepository")

    async def _get_session(self) -> AsyncSession:
        if self._session:
            return self._session
        return await get_session()

    # Approval Request Methods

    async def create_request(
        self,
        tenant_id: str,
        request: ApprovalRequestCreate,
    ) -> ApprovalRequestModel:
        """Create a new approval request."""
        session = await self._get_session()

        expires_at = datetime.utcnow() + timedelta(hours=request.expires_in_hours)

        approval = ApprovalRequestModel(
            tenant_id=tenant_id,
            agent_id=request.agent_id,
            execution_id=request.execution_id,
            action_id=request.action_id,
            approval_type=request.approval_type.value,
            priority=request.priority.value,
            title=request.title,
            description=request.description,
            action_summary=request.action_summary,
            context_data=request.context_data,
            assigned_to=request.assigned_to,
            expires_at=expires_at,
        )

        session.add(approval)
        await session.commit()
        await session.refresh(approval)

        self._logger.info(
            "Created approval request",
            approval_id=str(approval.id),
            agent_id=str(request.agent_id),
        )

        return approval

    async def get_by_id(
        self,
        approval_id: UUID,
        tenant_id: str,
    ) -> ApprovalRequestModel | None:
        """Get approval request by ID."""
        session = await self._get_session()

        result = await session.execute(
            select(ApprovalRequestModel).where(
                and_(
                    ApprovalRequestModel.id == approval_id,
                    ApprovalRequestModel.tenant_id == tenant_id,
                )
            )
        )

        return result.scalar_one_or_none()

    async def update_status(
        self,
        approval_id: UUID,
        tenant_id: str,
        status: ApprovalStatus,
        approved_by: str | None = None,
        notes: str | None = None,
        modifications: dict | None = None,
    ) -> bool:
        """Update approval request status."""
        session = await self._get_session()

        approval = await self.get_by_id(approval_id, tenant_id)
        if not approval:
            return False

        approval.status = status.value
        approval.responded_at = datetime.utcnow()

        if approved_by:
            approval.approved_by = approved_by
        if notes:
            approval.response_notes = notes
        if modifications:
            approval.modifications = modifications

        await session.commit()

        self._logger.info(
            "Updated approval status",
            approval_id=str(approval_id),
            status=status.value,
            approved_by=approved_by,
        )

        return True

    async def list_pending(
        self,
        tenant_id: str,
        assigned_to: str | None = None,
        agent_id: UUID | None = None,
        priority: ApprovalPriority | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ApprovalRequestModel], int]:
        """List pending approval requests."""
        session = await self._get_session()

        conditions = [
            ApprovalRequestModel.tenant_id == tenant_id,
            ApprovalRequestModel.status == ApprovalStatus.PENDING.value,
        ]

        if assigned_to:
            conditions.append(
                or_(
                    ApprovalRequestModel.assigned_to == assigned_to,
                    ApprovalRequestModel.assigned_to.is_(None),
                )
            )
        if agent_id:
            conditions.append(ApprovalRequestModel.agent_id == agent_id)
        if priority:
            conditions.append(ApprovalRequestModel.priority == priority.value)

        # Get total count
        count_result = await session.execute(
            select(func.count())
            .select_from(ApprovalRequestModel)
            .where(and_(*conditions))
        )
        total = count_result.scalar()

        # Get requests
        result = await session.execute(
            select(ApprovalRequestModel)
            .where(and_(*conditions))
            .order_by(
                # Priority order: urgent, high, medium, low
                ApprovalRequestModel.priority.desc(),
                ApprovalRequestModel.created_at.asc(),
            )
            .limit(limit)
            .offset(offset)
        )

        return result.scalars().all(), total

    async def list_by_execution(
        self,
        execution_id: UUID,
        tenant_id: str,
    ) -> list[ApprovalRequestModel]:
        """Get all approvals for an execution."""
        session = await self._get_session()

        result = await session.execute(
            select(ApprovalRequestModel).where(
                and_(
                    ApprovalRequestModel.execution_id == execution_id,
                    ApprovalRequestModel.tenant_id == tenant_id,
                )
            )
        )

        return result.scalars().all()

    async def expire_old_requests(self, tenant_id: str) -> int:
        """Expire requests past their expiration time."""
        session = await self._get_session()

        now = datetime.utcnow()

        result = await session.execute(
            update(ApprovalRequestModel)
            .where(
                and_(
                    ApprovalRequestModel.tenant_id == tenant_id,
                    ApprovalRequestModel.status == ApprovalStatus.PENDING.value,
                    ApprovalRequestModel.expires_at < now,
                )
            )
            .values(status=ApprovalStatus.EXPIRED.value)
        )

        await session.commit()

        count = result.rowcount
        if count > 0:
            self._logger.info("Expired old approval requests", count=count)

        return count

    async def get_stats(
        self,
        tenant_id: str,
        days: int = 7,
    ) -> dict[str, Any]:
        """Get approval statistics."""
        session = await self._get_session()

        since = datetime.utcnow() - timedelta(days=days)

        # Count by status
        status_result = await session.execute(
            select(
                ApprovalRequestModel.status,
                func.count(),
            )
            .where(
                and_(
                    ApprovalRequestModel.tenant_id == tenant_id,
                    ApprovalRequestModel.created_at >= since,
                )
            )
            .group_by(ApprovalRequestModel.status)
        )
        by_status = {row[0]: row[1] for row in status_result}

        # Average response time
        avg_result = await session.execute(
            select(
                func.avg(
                    func.extract(
                        "epoch",
                        ApprovalRequestModel.responded_at - ApprovalRequestModel.created_at,
                    )
                )
            )
            .where(
                and_(
                    ApprovalRequestModel.tenant_id == tenant_id,
                    ApprovalRequestModel.responded_at.isnot(None),
                    ApprovalRequestModel.created_at >= since,
                )
            )
        )
        avg_response_time = avg_result.scalar()

        return {
            "period_days": days,
            "by_status": by_status,
            "total_requests": sum(by_status.values()),
            "pending_count": by_status.get(ApprovalStatus.PENDING.value, 0),
            "average_response_time_seconds": int(avg_response_time) if avg_response_time else None,
            "approval_rate": (
                by_status.get(ApprovalStatus.APPROVED.value, 0) /
                (by_status.get(ApprovalStatus.APPROVED.value, 0) +
                 by_status.get(ApprovalStatus.REJECTED.value, 0))
                if by_status.get(ApprovalStatus.APPROVED.value, 0) +
                   by_status.get(ApprovalStatus.REJECTED.value, 0) > 0
                else None
            ),
        }

    # Approval Rules Methods

    async def create_rule(
        self,
        tenant_id: str,
        rule: ApprovalRuleCreate,
    ) -> ApprovalRuleModel:
        """Create an approval rule."""
        session = await self._get_session()

        db_rule = ApprovalRuleModel(
            tenant_id=tenant_id,
            name=rule.name,
            description=rule.description,
            enabled=rule.enabled,
            priority=rule.priority,
            agent_pattern=rule.agent_pattern,
            action_types=rule.action_types,
            trigger_types=rule.trigger_types,
            conditions=rule.conditions,
            approval_type=rule.approval_type,
            required_approvers=rule.required_approvers,
            approver_roles=rule.approver_roles,
            timeout_hours=rule.timeout_hours,
        )

        session.add(db_rule)
        await session.commit()
        await session.refresh(db_rule)

        return db_rule

    async def get_matching_rules(
        self,
        tenant_id: str,
        agent_name: str,
        action_type: str | None = None,
        trigger_type: str | None = None,
    ) -> list[ApprovalRuleModel]:
        """Get rules matching the given criteria."""
        import re

        session = await self._get_session()

        result = await session.execute(
            select(ApprovalRuleModel)
            .where(
                and_(
                    ApprovalRuleModel.tenant_id == tenant_id,
                    ApprovalRuleModel.enabled == True,
                )
            )
            .order_by(ApprovalRuleModel.priority.asc())
        )

        rules = result.scalars().all()
        matching = []

        for rule in rules:
            # Check agent pattern
            if rule.agent_pattern:
                try:
                    if not re.match(rule.agent_pattern, agent_name):
                        continue
                except re.error:
                    continue

            # Check action types
            if rule.action_types and action_type:
                if action_type not in rule.action_types:
                    continue

            # Check trigger types
            if rule.trigger_types and trigger_type:
                if trigger_type not in rule.trigger_types:
                    continue

            matching.append(rule)

        return matching

    async def list_rules(
        self,
        tenant_id: str,
        enabled_only: bool = False,
    ) -> list[ApprovalRuleModel]:
        """List all approval rules."""
        session = await self._get_session()

        conditions = [ApprovalRuleModel.tenant_id == tenant_id]
        if enabled_only:
            conditions.append(ApprovalRuleModel.enabled == True)

        result = await session.execute(
            select(ApprovalRuleModel)
            .where(and_(*conditions))
            .order_by(ApprovalRuleModel.priority.asc())
        )

        return result.scalars().all()

    async def update_rule(
        self,
        rule_id: UUID,
        tenant_id: str,
        updates: dict[str, Any],
    ) -> ApprovalRuleModel | None:
        """Update an approval rule."""
        session = await self._get_session()

        result = await session.execute(
            select(ApprovalRuleModel).where(
                and_(
                    ApprovalRuleModel.id == rule_id,
                    ApprovalRuleModel.tenant_id == tenant_id,
                )
            )
        )
        rule = result.scalar_one_or_none()

        if not rule:
            return None

        for key, value in updates.items():
            if hasattr(rule, key):
                setattr(rule, key, value)

        rule.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(rule)

        return rule

    async def delete_rule(
        self,
        rule_id: UUID,
        tenant_id: str,
    ) -> bool:
        """Delete an approval rule."""
        session = await self._get_session()

        result = await session.execute(
            select(ApprovalRuleModel).where(
                and_(
                    ApprovalRuleModel.id == rule_id,
                    ApprovalRuleModel.tenant_id == tenant_id,
                )
            )
        )
        rule = result.scalar_one_or_none()

        if not rule:
            return False

        await session.delete(rule)
        await session.commit()

        return True
```

### Step 3: Approval Service

```python
# services/agent-service/src/aswa_agents/services/approval_service.py
"""Approval service for human-in-the-loop workflows."""

from datetime import datetime
from typing import Any
from uuid import UUID

import structlog

from aswa_agents.models.approval import (
    ApprovalStatus,
    ApprovalPriority,
    ApprovalType,
    ApprovalRequestCreate,
    ApprovalDecision,
    ApprovalRuleModel,
)
from aswa_agents.repositories.approval_repository import ApprovalRepository

logger = structlog.get_logger()


class ApprovalService:
    """
    Service for managing approval workflows.

    Handles approval requests, rule matching, and notifications.
    """

    def __init__(self):
        self._repo = ApprovalRepository()
        self._logger = logger.bind(component="ApprovalService")

    async def check_requires_approval(
        self,
        tenant_id: str,
        agent_name: str,
        action_type: str,
        trigger_type: str,
        context: dict[str, Any],
    ) -> tuple[bool, ApprovalRuleModel | None]:
        """
        Check if an action requires approval.

        Returns (requires_approval, matching_rule).
        """
        rules = await self._repo.get_matching_rules(
            tenant_id=tenant_id,
            agent_name=agent_name,
            action_type=action_type,
            trigger_type=trigger_type,
        )

        if not rules:
            return False, None

        # Use first matching rule (highest priority)
        rule = rules[0]

        # Check conditions if any
        if rule.conditions:
            if not self._evaluate_conditions(rule.conditions, context):
                return False, None

        # Check approval type
        if rule.approval_type == "auto":
            return False, rule

        return True, rule

    def _evaluate_conditions(
        self,
        conditions: dict[str, Any],
        context: dict[str, Any],
    ) -> bool:
        """Evaluate rule conditions against context."""
        for field, expected in conditions.items():
            actual = self._get_nested_value(context, field)

            if isinstance(expected, dict):
                # Complex condition
                op = expected.get("op", "eq")
                value = expected.get("value")

                if op == "eq" and actual != value:
                    return False
                elif op == "ne" and actual == value:
                    return False
                elif op == "gt" and not (actual and actual > value):
                    return False
                elif op == "lt" and not (actual and actual < value):
                    return False
                elif op == "contains" and not (actual and value in actual):
                    return False
                elif op == "in" and actual not in value:
                    return False
            else:
                # Simple equality
                if actual != expected:
                    return False

        return True

    def _get_nested_value(self, data: dict, path: str) -> Any:
        """Get value from nested dict using dot notation."""
        current = data
        for part in path.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

    async def request_approval(
        self,
        tenant_id: str,
        agent_id: UUID,
        execution_id: UUID | None,
        action_id: str | None,
        title: str,
        description: str | None = None,
        action_summary: str | None = None,
        context_data: dict[str, Any] | None = None,
        priority: ApprovalPriority = ApprovalPriority.MEDIUM,
        approval_type: ApprovalType = ApprovalType.ACTION,
        assigned_to: str | None = None,
        timeout_hours: int = 24,
    ) -> UUID:
        """
        Create an approval request.

        Returns the approval request ID.
        """
        request = ApprovalRequestCreate(
            agent_id=agent_id,
            execution_id=execution_id,
            action_id=action_id,
            approval_type=approval_type,
            priority=priority,
            title=title,
            description=description,
            action_summary=action_summary,
            context_data=context_data or {},
            assigned_to=assigned_to,
            expires_in_hours=timeout_hours,
        )

        approval = await self._repo.create_request(tenant_id, request)

        # Send notification
        await self._send_notification(approval)

        self._logger.info(
            "Approval request created",
            approval_id=str(approval.id),
            agent_id=str(agent_id),
            priority=priority.value,
        )

        return approval.id

    async def approve(
        self,
        approval_id: UUID,
        tenant_id: str,
        approver: str,
        notes: str | None = None,
        modifications: dict[str, Any] | None = None,
    ) -> bool:
        """Approve a request."""
        success = await self._repo.update_status(
            approval_id=approval_id,
            tenant_id=tenant_id,
            status=ApprovalStatus.APPROVED,
            approved_by=approver,
            notes=notes,
            modifications=modifications,
        )

        if success:
            # Resume execution if applicable
            await self._resume_execution(approval_id, tenant_id)

            self._logger.info(
                "Approval request approved",
                approval_id=str(approval_id),
                approver=approver,
            )

        return success

    async def reject(
        self,
        approval_id: UUID,
        tenant_id: str,
        rejector: str,
        notes: str | None = None,
    ) -> bool:
        """Reject a request."""
        success = await self._repo.update_status(
            approval_id=approval_id,
            tenant_id=tenant_id,
            status=ApprovalStatus.REJECTED,
            approved_by=rejector,
            notes=notes,
        )

        if success:
            # Cancel execution if applicable
            await self._cancel_execution(approval_id, tenant_id)

            self._logger.info(
                "Approval request rejected",
                approval_id=str(approval_id),
                rejector=rejector,
            )

        return success

    async def cancel(
        self,
        approval_id: UUID,
        tenant_id: str,
    ) -> bool:
        """Cancel a pending request."""
        success = await self._repo.update_status(
            approval_id=approval_id,
            tenant_id=tenant_id,
            status=ApprovalStatus.CANCELLED,
        )

        if success:
            self._logger.info(
                "Approval request cancelled",
                approval_id=str(approval_id),
            )

        return success

    async def get_pending_for_user(
        self,
        tenant_id: str,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """Get pending approvals for a user."""
        requests, total = await self._repo.list_pending(
            tenant_id=tenant_id,
            assigned_to=user_id,
            limit=limit,
            offset=offset,
        )

        return [self._to_dict(r) for r in requests], total

    async def wait_for_approval(
        self,
        approval_id: UUID,
        tenant_id: str,
        timeout_seconds: int = 3600,
    ) -> tuple[ApprovalStatus, dict | None]:
        """
        Wait for an approval decision.

        Returns (status, modifications).
        Used by agent executor to pause execution.
        """
        import asyncio

        start = datetime.utcnow()
        poll_interval = 5  # seconds

        while True:
            approval = await self._repo.get_by_id(approval_id, tenant_id)

            if not approval:
                return ApprovalStatus.CANCELLED, None

            if approval.status != ApprovalStatus.PENDING.value:
                return ApprovalStatus(approval.status), approval.modifications

            # Check timeout
            elapsed = (datetime.utcnow() - start).total_seconds()
            if elapsed >= timeout_seconds:
                await self._repo.update_status(
                    approval_id, tenant_id, ApprovalStatus.EXPIRED
                )
                return ApprovalStatus.EXPIRED, None

            await asyncio.sleep(poll_interval)

    async def _send_notification(self, approval) -> None:
        """Send notification for approval request."""
        # Integration with notification service
        try:
            from aswa_agents.services.notification_client import NotificationClient

            client = NotificationClient()

            await client.send(
                tenant_id=approval.tenant_id,
                channel="approval",
                recipient=approval.assigned_to,
                title=f"Approval Required: {approval.title}",
                body=approval.description or approval.action_summary,
                data={
                    "approval_id": str(approval.id),
                    "agent_id": str(approval.agent_id),
                    "priority": approval.priority,
                    "expires_at": approval.expires_at.isoformat() if approval.expires_at else None,
                },
            )

            # Mark notification sent
            approval.notification_sent = True

        except Exception as e:
            self._logger.warning(
                "Failed to send approval notification",
                approval_id=str(approval.id),
                error=str(e),
            )

    async def _resume_execution(
        self,
        approval_id: UUID,
        tenant_id: str,
    ) -> None:
        """Resume paused execution after approval."""
        approval = await self._repo.get_by_id(approval_id, tenant_id)
        if not approval or not approval.execution_id:
            return

        # Signal execution to resume
        try:
            from aswa_agents.execution.orchestrator import ExecutionOrchestrator

            orchestrator = ExecutionOrchestrator()
            await orchestrator.resume_execution(
                execution_id=approval.execution_id,
                modifications=approval.modifications,
            )
        except Exception as e:
            self._logger.error(
                "Failed to resume execution",
                execution_id=str(approval.execution_id),
                error=str(e),
            )

    async def _cancel_execution(
        self,
        approval_id: UUID,
        tenant_id: str,
    ) -> None:
        """Cancel execution after rejection."""
        approval = await self._repo.get_by_id(approval_id, tenant_id)
        if not approval or not approval.execution_id:
            return

        try:
            from aswa_agents.execution.orchestrator import ExecutionOrchestrator

            orchestrator = ExecutionOrchestrator()
            await orchestrator.cancel_execution(
                execution_id=approval.execution_id,
                reason=f"Approval rejected: {approval.response_notes or 'No reason provided'}",
            )
        except Exception as e:
            self._logger.error(
                "Failed to cancel execution",
                execution_id=str(approval.execution_id),
                error=str(e),
            )

    def _to_dict(self, approval) -> dict:
        """Convert approval model to dict."""
        return {
            "id": str(approval.id),
            "agent_id": str(approval.agent_id),
            "execution_id": str(approval.execution_id) if approval.execution_id else None,
            "action_id": approval.action_id,
            "approval_type": approval.approval_type,
            "status": approval.status,
            "priority": approval.priority,
            "title": approval.title,
            "description": approval.description,
            "action_summary": approval.action_summary,
            "context_data": approval.context_data,
            "assigned_to": approval.assigned_to,
            "created_at": approval.created_at.isoformat(),
            "expires_at": approval.expires_at.isoformat() if approval.expires_at else None,
        }
```

### Step 4: Approval API Endpoints

```python
# services/agent-service/src/aswa_agents/api/approvals.py
"""API endpoints for approvals."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from aswa_agents.models.approval import (
    ApprovalStatus,
    ApprovalPriority,
    ApprovalType,
    ApprovalDecision,
    ApprovalRuleCreate,
)
from aswa_agents.services.approval_service import ApprovalService
from aswa_agents.repositories.approval_repository import ApprovalRepository

router = APIRouter(prefix="/approvals", tags=["approvals"])


class ApprovalListResponse(BaseModel):
    """Response for listing approvals."""

    approvals: list[dict[str, Any]]
    total: int
    limit: int
    offset: int


class ApprovalStatsResponse(BaseModel):
    """Response for approval statistics."""

    period_days: int
    by_status: dict[str, int]
    total_requests: int
    pending_count: int
    average_response_time_seconds: int | None
    approval_rate: float | None


class RuleListResponse(BaseModel):
    """Response for listing rules."""

    rules: list[dict[str, Any]]
    total: int


@router.get("", response_model=ApprovalListResponse)
async def list_pending_approvals(
    agent_id: UUID | None = None,
    priority: ApprovalPriority | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> ApprovalListResponse:
    """List pending approval requests."""
    tenant_id = "default-tenant"  # From auth in production

    repo = ApprovalRepository()
    requests, total = await repo.list_pending(
        tenant_id=tenant_id,
        agent_id=agent_id,
        priority=priority,
        limit=limit,
        offset=offset,
    )

    return ApprovalListResponse(
        approvals=[_to_dict(r) for r in requests],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/stats", response_model=ApprovalStatsResponse)
async def get_approval_stats(
    days: int = Query(7, ge=1, le=90),
) -> ApprovalStatsResponse:
    """Get approval statistics."""
    tenant_id = "default-tenant"

    repo = ApprovalRepository()
    stats = await repo.get_stats(tenant_id, days)

    return ApprovalStatsResponse(**stats)


@router.get("/{approval_id}")
async def get_approval(approval_id: UUID) -> dict[str, Any]:
    """Get approval request details."""
    tenant_id = "default-tenant"

    repo = ApprovalRepository()
    approval = await repo.get_by_id(approval_id, tenant_id)

    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")

    return _to_dict(approval)


@router.post("/{approval_id}/approve")
async def approve_request(
    approval_id: UUID,
    decision: ApprovalDecision,
) -> dict[str, Any]:
    """Approve a request."""
    tenant_id = "default-tenant"
    user_id = "current-user"  # From auth

    service = ApprovalService()
    success = await service.approve(
        approval_id=approval_id,
        tenant_id=tenant_id,
        approver=user_id,
        notes=decision.notes,
        modifications=decision.modifications,
    )

    if not success:
        raise HTTPException(status_code=404, detail="Approval not found")

    return {"status": "approved", "approval_id": str(approval_id)}


@router.post("/{approval_id}/reject")
async def reject_request(
    approval_id: UUID,
    decision: ApprovalDecision,
) -> dict[str, Any]:
    """Reject a request."""
    tenant_id = "default-tenant"
    user_id = "current-user"

    service = ApprovalService()
    success = await service.reject(
        approval_id=approval_id,
        tenant_id=tenant_id,
        rejector=user_id,
        notes=decision.notes,
    )

    if not success:
        raise HTTPException(status_code=404, detail="Approval not found")

    return {"status": "rejected", "approval_id": str(approval_id)}


@router.post("/{approval_id}/cancel")
async def cancel_request(approval_id: UUID) -> dict[str, Any]:
    """Cancel a pending request."""
    tenant_id = "default-tenant"

    service = ApprovalService()
    success = await service.cancel(approval_id, tenant_id)

    if not success:
        raise HTTPException(status_code=404, detail="Approval not found")

    return {"status": "cancelled", "approval_id": str(approval_id)}


# Approval Rules endpoints

@router.get("/rules", response_model=RuleListResponse)
async def list_rules(
    enabled_only: bool = False,
) -> RuleListResponse:
    """List approval rules."""
    tenant_id = "default-tenant"

    repo = ApprovalRepository()
    rules = await repo.list_rules(tenant_id, enabled_only)

    return RuleListResponse(
        rules=[_rule_to_dict(r) for r in rules],
        total=len(rules),
    )


@router.post("/rules")
async def create_rule(rule: ApprovalRuleCreate) -> dict[str, Any]:
    """Create an approval rule."""
    tenant_id = "default-tenant"

    repo = ApprovalRepository()
    created = await repo.create_rule(tenant_id, rule)

    return _rule_to_dict(created)


@router.put("/rules/{rule_id}")
async def update_rule(
    rule_id: UUID,
    updates: dict[str, Any],
) -> dict[str, Any]:
    """Update an approval rule."""
    tenant_id = "default-tenant"

    repo = ApprovalRepository()
    updated = await repo.update_rule(rule_id, tenant_id, updates)

    if not updated:
        raise HTTPException(status_code=404, detail="Rule not found")

    return _rule_to_dict(updated)


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: UUID) -> dict[str, Any]:
    """Delete an approval rule."""
    tenant_id = "default-tenant"

    repo = ApprovalRepository()
    success = await repo.delete_rule(rule_id, tenant_id)

    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")

    return {"deleted": True, "rule_id": str(rule_id)}


def _to_dict(approval) -> dict[str, Any]:
    """Convert approval to dict."""
    return {
        "id": str(approval.id),
        "agent_id": str(approval.agent_id),
        "execution_id": str(approval.execution_id) if approval.execution_id else None,
        "action_id": approval.action_id,
        "approval_type": approval.approval_type,
        "status": approval.status,
        "priority": approval.priority,
        "title": approval.title,
        "description": approval.description,
        "action_summary": approval.action_summary,
        "context_data": approval.context_data,
        "assigned_to": approval.assigned_to,
        "approved_by": approval.approved_by,
        "response_notes": approval.response_notes,
        "created_at": approval.created_at.isoformat(),
        "expires_at": approval.expires_at.isoformat() if approval.expires_at else None,
        "responded_at": approval.responded_at.isoformat() if approval.responded_at else None,
    }


def _rule_to_dict(rule) -> dict[str, Any]:
    """Convert rule to dict."""
    return {
        "id": str(rule.id),
        "name": rule.name,
        "description": rule.description,
        "enabled": rule.enabled,
        "priority": rule.priority,
        "agent_pattern": rule.agent_pattern,
        "action_types": rule.action_types,
        "trigger_types": rule.trigger_types,
        "conditions": rule.conditions,
        "approval_type": rule.approval_type,
        "required_approvers": rule.required_approvers,
        "approver_roles": rule.approver_roles,
        "timeout_hours": rule.timeout_hours,
        "created_at": rule.created_at.isoformat(),
        "updated_at": rule.updated_at.isoformat(),
    }
```

## Test Cases

```python
# services/agent-service/tests/unit/test_approval_service.py
"""Tests for approval service."""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, patch

from aswa_agents.models.approval import (
    ApprovalStatus,
    ApprovalPriority,
    ApprovalType,
    ApprovalRequestCreate,
)
from aswa_agents.services.approval_service import ApprovalService
from aswa_agents.repositories.approval_repository import ApprovalRepository


class TestApprovalRepository:
    """Test ApprovalRepository."""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_create_request(self, mock_session):
        """Test creating approval request."""
        repo = ApprovalRepository(session=mock_session)

        request = ApprovalRequestCreate(
            agent_id=uuid4(),
            title="Test Approval",
            description="Test description",
            priority=ApprovalPriority.HIGH,
        )

        result = await repo.create_request("test-tenant", request)

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_status(self, mock_session):
        """Test updating approval status."""
        repo = ApprovalRepository(session=mock_session)

        approval_id = uuid4()
        mock_approval = AsyncMock()
        mock_session.execute.return_value = AsyncMock(
            scalar_one_or_none=lambda: mock_approval
        )

        result = await repo.update_status(
            approval_id,
            "test-tenant",
            ApprovalStatus.APPROVED,
            approved_by="user@example.com",
        )

        assert mock_approval.status == ApprovalStatus.APPROVED.value
        mock_session.commit.assert_called()


class TestApprovalService:
    """Test ApprovalService."""

    @pytest.fixture
    def service(self):
        return ApprovalService()

    @pytest.mark.asyncio
    async def test_check_requires_approval_no_rules(self, service):
        """Test when no rules match."""
        with patch.object(service._repo, "get_matching_rules") as mock:
            mock.return_value = []

            requires, rule = await service.check_requires_approval(
                tenant_id="test",
                agent_name="test-agent",
                action_type="send_email",
                trigger_type="email",
                context={},
            )

            assert requires is False
            assert rule is None

    @pytest.mark.asyncio
    async def test_check_requires_approval_with_rule(self, service):
        """Test when rule matches."""
        mock_rule = AsyncMock()
        mock_rule.approval_type = "review"
        mock_rule.conditions = {}

        with patch.object(service._repo, "get_matching_rules") as mock:
            mock.return_value = [mock_rule]

            requires, rule = await service.check_requires_approval(
                tenant_id="test",
                agent_name="test-agent",
                action_type="send_email",
                trigger_type="email",
                context={},
            )

            assert requires is True
            assert rule == mock_rule

    @pytest.mark.asyncio
    async def test_check_requires_approval_auto_rule(self, service):
        """Test auto approval rule."""
        mock_rule = AsyncMock()
        mock_rule.approval_type = "auto"
        mock_rule.conditions = {}

        with patch.object(service._repo, "get_matching_rules") as mock:
            mock.return_value = [mock_rule]

            requires, rule = await service.check_requires_approval(
                tenant_id="test",
                agent_name="test-agent",
                action_type="send_email",
                trigger_type="email",
                context={},
            )

            assert requires is False
            assert rule == mock_rule

    @pytest.mark.asyncio
    async def test_request_approval(self, service):
        """Test creating approval request."""
        mock_approval = AsyncMock()
        mock_approval.id = uuid4()
        mock_approval.tenant_id = "test"
        mock_approval.assigned_to = None
        mock_approval.title = "Test"
        mock_approval.description = None
        mock_approval.action_summary = None
        mock_approval.expires_at = None
        mock_approval.agent_id = uuid4()
        mock_approval.priority = "medium"
        mock_approval.notification_sent = False

        with patch.object(service._repo, "create_request") as mock:
            mock.return_value = mock_approval

            approval_id = await service.request_approval(
                tenant_id="test",
                agent_id=uuid4(),
                execution_id=uuid4(),
                action_id="action_1",
                title="Test Approval",
            )

            assert approval_id == mock_approval.id
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_approve(self, service):
        """Test approving request."""
        with patch.object(service._repo, "update_status") as mock_status:
            mock_status.return_value = True
            with patch.object(service, "_resume_execution") as mock_resume:
                success = await service.approve(
                    approval_id=uuid4(),
                    tenant_id="test",
                    approver="user@example.com",
                    notes="Looks good",
                )

                assert success is True
                mock_resume.assert_called_once()

    @pytest.mark.asyncio
    async def test_reject(self, service):
        """Test rejecting request."""
        with patch.object(service._repo, "update_status") as mock_status:
            mock_status.return_value = True
            with patch.object(service, "_cancel_execution") as mock_cancel:
                success = await service.reject(
                    approval_id=uuid4(),
                    tenant_id="test",
                    rejector="user@example.com",
                    notes="Not approved",
                )

                assert success is True
                mock_cancel.assert_called_once()

    def test_evaluate_conditions(self, service):
        """Test condition evaluation."""
        conditions = {
            "priority": "high",
            "amount": {"op": "gt", "value": 100},
        }

        context = {
            "priority": "high",
            "amount": 150,
        }

        result = service._evaluate_conditions(conditions, context)
        assert result is True

        # Test failing condition
        context["priority"] = "low"
        result = service._evaluate_conditions(conditions, context)
        assert result is False


class TestApprovalRules:
    """Test approval rules."""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_get_matching_rules(self, mock_session):
        """Test matching rules by criteria."""
        from aswa_agents.models.approval import ApprovalRuleCreate

        repo = ApprovalRepository(session=mock_session)

        # Create mock rules
        rule1 = AsyncMock()
        rule1.agent_pattern = ".*email.*"
        rule1.action_types = ["send_email"]
        rule1.trigger_types = []

        rule2 = AsyncMock()
        rule2.agent_pattern = None
        rule2.action_types = []
        rule2.trigger_types = []

        mock_session.execute.return_value = AsyncMock(
            scalars=lambda: AsyncMock(all=lambda: [rule1, rule2])
        )

        rules = await repo.get_matching_rules(
            tenant_id="test",
            agent_name="email-processor",
            action_type="send_email",
        )

        assert len(rules) == 2

    @pytest.mark.asyncio
    async def test_rule_pattern_matching(self, mock_session):
        """Test rule pattern matching."""
        repo = ApprovalRepository(session=mock_session)

        rule = AsyncMock()
        rule.agent_pattern = "^support-.*"
        rule.action_types = []
        rule.trigger_types = []

        mock_session.execute.return_value = AsyncMock(
            scalars=lambda: AsyncMock(all=lambda: [rule])
        )

        # Should match
        rules = await repo.get_matching_rules(
            tenant_id="test",
            agent_name="support-bot",
        )
        assert len(rules) == 1

        # Should not match (if pattern is enforced in implementation)
        # This depends on actual implementation logic
```

## Verification Steps

1. **Run unit tests:**
   ```bash
   cd services/agent-service
   pytest tests/unit/test_approval_service.py -v
   ```

2. **Test approval flow:**
   ```python
   from aswa_agents.services.approval_service import ApprovalService
   from aswa_agents.models.approval import ApprovalPriority
   from uuid import uuid4

   service = ApprovalService()

   # Create approval
   approval_id = await service.request_approval(
       tenant_id="test",
       agent_id=uuid4(),
       execution_id=uuid4(),
       action_id="send_email_1",
       title="Send email to customers",
       description="Agent wants to send 100 emails",
       priority=ApprovalPriority.HIGH,
   )

   # Approve
   await service.approve(
       approval_id=approval_id,
       tenant_id="test",
       approver="admin@example.com",
       notes="Approved for sending",
   )
   ```

3. **Test API endpoints:**
   ```bash
   # List pending approvals
   curl http://localhost:8000/api/v1/approvals

   # Get specific approval
   curl http://localhost:8000/api/v1/approvals/{id}

   # Approve
   curl -X POST http://localhost:8000/api/v1/approvals/{id}/approve \
     -H "Content-Type: application/json" \
     -d '{"approved": true, "notes": "Looks good"}'

   # Create rule
   curl -X POST http://localhost:8000/api/v1/approvals/rules \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Email Approval",
       "action_types": ["send_email"],
       "approval_type": "review",
       "timeout_hours": 24
     }'
   ```

## Next Task

Proceed to `task-9.6.2-approval-ui.md` for implementing the approval UI.
