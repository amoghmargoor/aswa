"""SQLAlchemy models for agent persistence."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
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


def utcnow():
    """Get current UTC time."""
    return datetime.now(timezone.utc)


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
        DateTime, nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
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
        DateTime, nullable=False, default=utcnow
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
        DateTime, nullable=False, default=utcnow
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
        DateTime, nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        Index("ix_template_category", "category"),
        Index("ix_template_tenant_public", "tenant_id", "is_public"),
    )
