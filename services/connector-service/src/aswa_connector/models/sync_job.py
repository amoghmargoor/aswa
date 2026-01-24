"""Sync job database model."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import String, Text, Integer, BigInteger, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from aswa_common.db.base import Base


class SyncJobModel(Base):
    """Sync job model."""

    __tablename__ = "sync_jobs"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    connection_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
    )
    sync_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="incremental",
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    records_synced: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bytes_synced: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Provider job ID
    provider_job_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
