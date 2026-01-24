"""Connection database model."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import String, Text, Boolean, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from aswa_common.db.base import Base


class ConnectionModel(Base):
    """Data source connection model."""

    __tablename__ = "connections"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    connector_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
    )
    config: Mapped[dict] = mapped_column(JSON, nullable=True)
    sync_schedule: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sync_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="incremental",
    )
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Provider mapping
    provider_source_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_connection_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
