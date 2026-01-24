"""Document service for document storage and retrieval."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from redis.asyncio import Redis
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from aswa_common.logging import get_logger

from aswa_ingestion.config import settings

logger = get_logger(__name__)


class DocumentService:
    """Handles document storage and retrieval.

    Responsibilities:
    - Store and retrieve documents
    - Check for duplicates by content hash
    - Manage document processing status
    - Queue documents for processing
    """

    PROCESSING_QUEUE = "documents:processing:queue"
    PROCESSING_STATUS_PREFIX = "documents:status:"

    def __init__(self, db: AsyncSession, redis: Redis | None):
        """Initialize document service.

        Args:
            db: Async database session
            redis: Redis client (optional for some operations)
        """
        self.db = db
        self.redis = redis

    async def store_document(
        self,
        tenant_id: UUID,
        data_source_id: UUID,
        external_id: str,
        title: str,
        content: bytes,
        content_type: str,
        content_hash: str,
        file_size: int,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        """Store a new document.

        Args:
            tenant_id: Tenant ID
            data_source_id: Data source ID
            external_id: External ID from source system
            title: Document title
            content: Raw document content
            content_type: MIME type
            content_hash: SHA-256 hash of content
            file_size: Size in bytes
            metadata: Optional metadata

        Returns:
            Created document entity
        """
        from aswa_common.db.models import Document

        logger.info(
            f"Storing document: title={title}, content_type={content_type}, "
            f"size={file_size}, hash={content_hash[:16]}..."
        )

        # Create document entity
        document = Document(
            id=uuid4(),
            tenant_id=tenant_id,
            data_source_id=data_source_id,
            external_id=external_id,
            title=title,
            content=content.decode("utf-8", errors="replace") if content else None,
            content_type=content_type,
            content_hash=content_hash,
            metadata=metadata or {},
            file_size=file_size,
            processed_status="pending",
        )

        self.db.add(document)
        await self.db.flush()
        await self.db.refresh(document)

        logger.info(f"Document stored: id={document.id}")
        return document

    async def get_document(self, doc_id: UUID, tenant_id: UUID) -> Any | None:
        """Get document by ID.

        Args:
            doc_id: Document ID
            tenant_id: Tenant ID for authorization

        Returns:
            Document if found and belongs to tenant
        """
        from aswa_common.db.models import Document

        logger.debug(f"Getting document {doc_id} for tenant {tenant_id}")

        stmt = select(Document).where(
            Document.id == doc_id,
            Document.tenant_id == tenant_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def check_duplicate(
        self,
        content_hash: str,
        tenant_id: UUID,
    ) -> Any | None:
        """Check if document with same content hash exists.

        Args:
            content_hash: SHA-256 hash of content
            tenant_id: Tenant ID

        Returns:
            Existing document if found
        """
        from aswa_common.db.models import Document

        logger.debug(f"Checking for duplicate: hash={content_hash[:16]}...")

        stmt = select(Document).where(
            Document.content_hash == content_hash,
            Document.tenant_id == tenant_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_status(
        self,
        doc_id: UUID,
        status: str,
        error: str | None = None,
    ) -> None:
        """Update document processing status.

        Args:
            doc_id: Document ID
            status: New status (pending, processing, completed, failed)
            error: Optional error message if failed
        """
        from aswa_common.db.models import Document

        logger.info(f"Updating document {doc_id} status to {status}")

        document = await self.db.get(Document, doc_id)
        if document:
            document.processed_status = status
            if error:
                document.error_message = error
            if status == "completed":
                document.processed_at = datetime.now(timezone.utc)
            await self.db.flush()

    async def queue_for_processing(self, doc_id: UUID) -> None:
        """Queue document for processing.

        Args:
            doc_id: Document ID to queue
        """
        if self.redis is None:
            logger.warning("Redis not available, cannot queue document")
            return

        logger.debug(f"Queueing document {doc_id} for processing")

        await self.redis.rpush(self.PROCESSING_QUEUE, str(doc_id))
        await self.redis.set(
            f"{self.PROCESSING_STATUS_PREFIX}{doc_id}",
            "queued",
            ex=3600,
        )

    async def reset_for_reprocessing(self, doc_id: UUID) -> None:
        """Reset document for reprocessing.

        This deletes existing chunks and resets the status.

        Args:
            doc_id: Document ID
        """
        from aswa_common.db.models import DocumentChunk

        logger.info(f"Resetting document {doc_id} for reprocessing")

        # Delete existing chunks
        stmt = delete(DocumentChunk).where(DocumentChunk.document_id == doc_id)
        await self.db.execute(stmt)

        # Reset status
        await self.update_status(doc_id, "pending")

        # TODO: Delete embeddings from vector store

    async def delete_document(self, doc_id: UUID) -> None:
        """Delete document and all associated data.

        Args:
            doc_id: Document ID to delete
        """
        from aswa_common.db.models import Document, DocumentChunk

        logger.info(f"Deleting document {doc_id}")

        # Delete chunks first (foreign key constraint)
        chunk_stmt = delete(DocumentChunk).where(DocumentChunk.document_id == doc_id)
        await self.db.execute(chunk_stmt)

        # Delete document
        doc_stmt = delete(Document).where(Document.id == doc_id)
        await self.db.execute(doc_stmt)

        await self.db.flush()

        # TODO: Delete from blob storage
        # TODO: Delete embeddings from vector store

    async def get_chunks(self, doc_id: UUID) -> list[Any]:
        """Get all chunks for a document.

        Args:
            doc_id: Document ID

        Returns:
            List of document chunks
        """
        from aswa_common.db.models import DocumentChunk

        logger.debug(f"Getting chunks for document {doc_id}")

        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == doc_id)
            .order_by(DocumentChunk.chunk_index)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_pending_documents(self, limit: int = 100) -> list[Any]:
        """Get documents pending processing.

        Args:
            limit: Maximum number of documents to return

        Returns:
            List of pending documents
        """
        from aswa_common.db.models import Document

        logger.debug(f"Getting up to {limit} pending documents")

        stmt = (
            select(Document)
            .where(Document.processed_status == "pending")
            .order_by(Document.created_at.asc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
