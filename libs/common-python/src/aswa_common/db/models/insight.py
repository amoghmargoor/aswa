"""Insight and EntityRelationship models."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ARRAY, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from aswa_common.db.models.base import Base, TimestampMixin, TenantMixin


class Insight(Base, TimestampMixin, TenantMixin):
    """Insight model for AI-generated insights."""

    __tablename__ = "insights"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    insight_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False)
    severity: Mapped[str | None] = mapped_column(String(50))
    category: Mapped[str | None] = mapped_column(String(100))
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    source_documents: Mapped[list[UUID]] = mapped_column(ARRAY(UUID), nullable=False)
    evidence_snippets: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    user_feedback: Mapped[str | None] = mapped_column(String(50))
    feedback_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    feedback_comment: Mapped[str | None] = mapped_column(Text)
    feedback_at: Mapped[datetime | None]
    vector_id: Mapped[str | None] = mapped_column(String(100))

    def __repr__(self) -> str:
        return f"<Insight(id={self.id}, type='{self.insight_type}', title='{self.title}')>"


class EntityRelationship(Base, TenantMixin):
    """Entity relationship model for connections between insights."""

    __tablename__ = "entity_relationships"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_insight_id: Mapped[UUID] = mapped_column(
        ForeignKey("insights.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_insight_id: Mapped[UUID] = mapped_column(
        ForeignKey("insights.id", ondelete="CASCADE"),
        nullable=False,
    )
    relationship_type: Mapped[str] = mapped_column(String(100), nullable=False)
    direction: Mapped[str] = mapped_column(String(20), nullable=False, default="directed")
    confidence: Mapped[float] = mapped_column(nullable=False)
    evidence: Mapped[str | None] = mapped_column(Text)
    metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<EntityRelationship(id={self.id}, type='{self.relationship_type}', source={self.source_insight_id}, target={self.target_insight_id})>"
