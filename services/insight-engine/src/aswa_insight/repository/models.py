from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Column,
    String,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    Index,
    UniqueConstraint,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB, ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from aswa_insight.models.insights import InsightType
from aswa_insight.models.risks import Severity
from aswa_insight.models.opportunities import ImpactLevel


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class InsightModel(Base):
    """SQLAlchemy model for insights."""

    __tablename__ = "insights"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    document_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)

    insight_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    title_normalized: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    # Type-specific fields
    severity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    impact: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Raw extraction data
    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    sources: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # Deduplication
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    is_duplicate_of: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("insights.id"), nullable=True)
    merge_count: Mapped[int] = mapped_column(default=1)

    # Validation
    user_validated: Mapped[bool] = mapped_column(Boolean, default=False)
    validation_status: Mapped[str | None] = mapped_column(String(50), nullable=True)  # confirmed, rejected, modified

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    extracted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Soft delete
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    feedback: Mapped[list["InsightFeedbackModel"]] = relationship(back_populates="insight")
    related_entities: Mapped[list["InsightEntityModel"]] = relationship(back_populates="insight")

    __table_args__ = (
        Index("ix_insights_tenant_type", "tenant_id", "insight_type"),
        Index("ix_insights_tenant_document", "tenant_id", "document_id"),
        Index("ix_insights_tenant_hash", "tenant_id", "content_hash"),
        Index("ix_insights_confidence", "confidence"),
    )


class EntityModel(Base):
    """SQLAlchemy model for extracted entities."""

    __tablename__ = "entities"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(500), nullable=False)
    name_normalized: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    aliases: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Aggregated confidence (from multiple extractions)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    mention_count: Mapped[int] = mapped_column(default=1)

    # Canonical entity reference (for deduplication)
    canonical_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("entities.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_entities_tenant_name", "tenant_id", "name_normalized"),
        UniqueConstraint("tenant_id", "name_normalized", "entity_type", name="uq_entity_tenant_name_type"),
    )


class InsightEntityModel(Base):
    """Junction table linking insights to entities."""

    __tablename__ = "insight_entities"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    insight_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("insights.id"), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("entities.id"), nullable=False)
    relationship_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    insight: Mapped["InsightModel"] = relationship(back_populates="related_entities")

    __table_args__ = (
        UniqueConstraint("insight_id", "entity_id", name="uq_insight_entity"),
    )


class InsightFeedbackModel(Base):
    """User feedback on insights."""

    __tablename__ = "insight_feedback"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    insight_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("insights.id"), nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)

    rating: Mapped[int | None] = mapped_column(nullable=True)  # 1-5
    is_accurate: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    correction: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    insight: Mapped["InsightModel"] = relationship(back_populates="feedback")

    __table_args__ = (
        Index("ix_feedback_insight", "insight_id"),
        UniqueConstraint("insight_id", "user_id", name="uq_feedback_insight_user"),
    )
