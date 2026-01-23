"""Database layer with SQLAlchemy models and repositories."""

from aswa_common.db.engine import create_engine
from aswa_common.db.models import (
    Base,
    DataSource,
    Document,
    DocumentChunk,
    EntityRelationship,
    Insight,
    Tenant,
    TenantMixin,
    TimestampMixin,
    User,
)
from aswa_common.db.repositories import (
    BaseRepository,
    DocumentRepository,
    InsightRepository,
    TenantScopedRepository,
)
from aswa_common.db.session import AsyncSessionFactory, get_db

__all__ = [
    # Engine
    "create_engine",
    # Session
    "AsyncSessionFactory",
    "get_db",
    # Models
    "Base",
    "TimestampMixin",
    "TenantMixin",
    "Tenant",
    "User",
    "DataSource",
    "Document",
    "DocumentChunk",
    "Insight",
    "EntityRelationship",
    # Repositories
    "BaseRepository",
    "TenantScopedRepository",
    "DocumentRepository",
    "InsightRepository",
]
