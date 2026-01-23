"""Repository classes for database operations."""

from aswa_common.db.repositories.base import BaseRepository, TenantScopedRepository
from aswa_common.db.repositories.document_repository import DocumentRepository
from aswa_common.db.repositories.insight_repository import InsightRepository

__all__ = [
    "BaseRepository",
    "TenantScopedRepository",
    "DocumentRepository",
    "InsightRepository",
]
