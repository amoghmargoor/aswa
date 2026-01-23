"""Document, DataSource, and DocumentChunk models."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aswa_common.db.models.base import Base, TimestampMixin, TenantMixin

if TYPE_CHECKING:
    from aswa_common.db.models.tenant import Tenant


class DataSource(Base, TimestampMixin, TenantMixin):
    """Data source model for external integrations."""

    __tablename__ = "data_sources"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    credentials_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    last_sync_at: Mapped[datetime | None]
    sync_cursor: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    sync_frequency_minutes: Mapped[int] = mapped_column(nullable=False, default=60)

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="data_sources")
    documents: Mapped[list["Document"]] = relationship(
        back_populates="data_source",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<DataSource(id={self.id}, type='{self.source_type}', name='{self.name}')>"


class Document(Base, TimestampMixin, TenantMixin):
    """Document model for ingested content."""

    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "data_source_id",
            "external_id",
            name="uq_documents_tenant_source_external",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    data_source_id: Mapped[UUID] = mapped_column(
        ForeignKey("data_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    external_id: Mapped[str] = mapped_column(String(500), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str | None] = mapped_column(String(1000))
    content: Mapped[str | None] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    source_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    processed_status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    processed_at: Mapped[datetime | None]
    error_message: Mapped[str | None] = mapped_column(Text)
    word_count: Mapped[int | None]
    language: Mapped[str | None] = mapped_column(String(10))

    # Relationships
    data_source: Mapped["DataSource"] = relationship(back_populates="documents")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, type='{self.content_type}', title='{self.title}')>"


class DocumentChunk(Base):
    """Document chunk model for vector embedding."""

    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunks_document_index"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(nullable=False)
    vector_id: Mapped[str | None] = mapped_column(String(100))
    start_char: Mapped[int | None]
    end_char: Mapped[int | None]
    metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    document: Mapped["Document"] = relationship(back_populates="chunks")

    def __repr__(self) -> str:
        return f"<DocumentChunk(id={self.id}, document_id={self.document_id}, index={self.chunk_index})>"


# Import at the end to avoid circular imports
from sqlalchemy import func  # noqa: E402
