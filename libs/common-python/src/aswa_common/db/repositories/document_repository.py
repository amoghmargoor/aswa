"""Document repository with specialized queries."""

from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from aswa_common.db.models.document import Document
from aswa_common.db.repositories.base import TenantScopedRepository
from aswa_common.logging import get_logger
from aswa_common.models import PageRequest, PageResponse

logger = get_logger(__name__)


class DocumentRepository(TenantScopedRepository[Document]):
    """Repository for document-specific operations."""

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        """Initialize document repository.

        Args:
            session: Async database session
            tenant_id: Tenant ID for isolation
        """
        super().__init__(session, Document, tenant_id)

    async def find_by_hash(self, content_hash: str) -> Document | None:
        """Find document by content hash within tenant.

        Args:
            content_hash: Content hash (SHA-256)

        Returns:
            Document if found, None otherwise
        """
        logger.debug(f"Finding document by hash={content_hash} for tenant={self.tenant_id}")
        stmt = select(Document).where(
            Document.tenant_id == self.tenant_id,
            Document.content_hash == content_hash,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_external_id(
        self,
        data_source_id: UUID,
        external_id: str,
    ) -> Document | None:
        """Find document by data source and external ID.

        Args:
            data_source_id: Data source ID
            external_id: External ID from source system

        Returns:
            Document if found, None otherwise
        """
        logger.debug(
            f"Finding document by source={data_source_id}, external_id={external_id} for tenant={self.tenant_id}"
        )
        stmt = select(Document).where(
            Document.tenant_id == self.tenant_id,
            Document.data_source_id == data_source_id,
            Document.external_id == external_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_pending(self, limit: int = 100) -> list[Document]:
        """Find documents pending processing.

        Args:
            limit: Maximum number of documents to return

        Returns:
            List of pending documents
        """
        logger.debug(f"Finding up to {limit} pending documents for tenant={self.tenant_id}")
        stmt = (
            select(Document)
            .where(
                Document.tenant_id == self.tenant_id,
                Document.processed_status == "pending",
            )
            .order_by(Document.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(
        self,
        id: UUID,
        status: str,
        error_message: str | None = None,
    ) -> None:
        """Update document processing status.

        Args:
            id: Document ID
            status: New status (pending, processing, completed, failed, skipped)
            error_message: Optional error message if failed
        """
        logger.debug(f"Updating document {id} status to {status} for tenant={self.tenant_id}")
        document = await self.get_by_id(id)
        if document:
            document.processed_status = status
            if error_message:
                document.error_message = error_message
            if status == "completed":
                from datetime import datetime, timezone

                document.processed_at = datetime.now(timezone.utc)
            await self.session.flush()

    async def search_fulltext(
        self,
        query: str,
        page: PageRequest,
    ) -> PageResponse[Document]:
        """Full-text search across documents.

        Args:
            query: Search query
            page: Pagination request

        Returns:
            Paginated search results
        """
        logger.debug(f"Full-text search for '{query}' in documents for tenant={self.tenant_id}")

        # PostgreSQL full-text search using to_tsvector and to_tsquery
        # Count matching documents
        count_stmt = (
            select(func.count())
            .select_from(Document)
            .where(
                Document.tenant_id == self.tenant_id,
                text(
                    "to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content, '')) "
                    "@@ to_tsquery('english', :query)"
                ).bindparams(query=query.replace(" ", " & ")),
            )
        )
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar_one()

        # Search with ranking
        stmt = (
            select(Document)
            .where(
                Document.tenant_id == self.tenant_id,
                text(
                    "to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content, '')) "
                    "@@ to_tsquery('english', :query)"
                ).bindparams(query=query.replace(" ", " & ")),
            )
            .order_by(
                text(
                    "ts_rank(to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content, '')), "
                    "to_tsquery('english', :query)) DESC"
                ).bindparams(query=query.replace(" ", " & "))
            )
            .offset(page.page * page.size)
            .limit(page.size)
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())

        import math

        total_pages = math.ceil(total / page.size) if page.size > 0 else 0

        return PageResponse(
            content=items,
            total_elements=total,
            total_pages=total_pages,
            current_page=page.page,
            page_size=page.size,
        )
