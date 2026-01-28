"""Job handlers for document processing worker."""

from typing import Any, Protocol
from uuid import UUID

import structlog
from prometheus_client import Counter, Histogram

logger = structlog.get_logger()


# Metrics
DOCUMENTS_PROCESSED = Counter(
    "handler_documents_processed_total",
    "Total documents processed",
    ["status", "content_type"],
)

CHUNKS_CREATED = Counter(
    "handler_chunks_created_total",
    "Total chunks created",
)

VECTORS_STORED = Counter(
    "handler_vectors_stored_total",
    "Total vectors stored",
)

PROCESSING_DURATION = Histogram(
    "handler_processing_duration_seconds",
    "Document processing duration by stage",
    ["stage"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)


class SessionFactory(Protocol):
    """Protocol for async session factory."""

    async def __call__(self) -> Any:
        """Create a new session."""
        ...


class DocumentRepository(Protocol):
    """Protocol for document repository."""

    async def get_by_id(self, document_id: UUID) -> Any:
        """Get document by ID."""
        ...

    async def update_status(
        self, document_id: UUID, status: str, error: str | None = None
    ) -> None:
        """Update document status."""
        ...


class ProcessingPipeline(Protocol):
    """Protocol for document processing pipeline."""

    async def process(self, document: Any) -> Any:
        """Process a document."""
        ...


class DocumentProcessingHandler:
    """Handler for document processing jobs.

    Processes documents through the ingestion pipeline:
    1. Fetch document from database
    2. Update status to processing
    3. Run through processing pipeline (parse, chunk, embed, store)
    4. Update status on completion/failure
    """

    def __init__(
        self,
        session_factory: SessionFactory,
        pipeline: ProcessingPipeline,
        repository_cls: type | None = None,
    ) -> None:
        """Initialize handler.

        Args:
            session_factory: Factory for creating database sessions
            pipeline: Document processing pipeline
            repository_cls: Document repository class (optional, for testing)
        """
        self.session_factory = session_factory
        self.pipeline = pipeline
        self._repository_cls = repository_cls

    async def __call__(self, payload: dict[str, Any]) -> None:
        """Process a document.

        Payload format:
        {
            "document_id": "uuid",
            "tenant_id": "uuid",
            "reprocess": false,
            "priority": 0
        }

        Args:
            payload: Job payload

        Raises:
            ValueError: If required fields missing
            Exception: If processing fails
        """
        # Validate payload
        document_id = self._get_uuid(payload, "document_id")
        tenant_id = self._get_uuid(payload, "tenant_id")
        reprocess = payload.get("reprocess", False)

        logger.info(
            "Processing document",
            document_id=str(document_id),
            tenant_id=str(tenant_id),
            reprocess=reprocess,
        )

        async with self.session_factory() as session:
            # Get repository
            repo = await self._get_repository(session, tenant_id)

            # Fetch document
            document = await repo.get_by_id(document_id)

            if not document:
                logger.warning("Document not found", document_id=str(document_id))
                return

            # Check if already processed
            if hasattr(document, "processed_status"):
                if document.processed_status == "completed" and not reprocess:
                    logger.info(
                        "Document already processed",
                        document_id=str(document_id),
                    )
                    return

            # Update status to processing
            await repo.update_status(document_id, "processing")

            try:
                # Run processing pipeline
                result = await self.pipeline.process(document)

                # Update metrics
                content_type = getattr(document, "content_type", "unknown")
                DOCUMENTS_PROCESSED.labels(status="success", content_type=content_type).inc()

                if hasattr(result, "chunks_created"):
                    CHUNKS_CREATED.inc(result.chunks_created)
                if hasattr(result, "vectors_stored"):
                    VECTORS_STORED.inc(result.vectors_stored)

                # Update status to completed
                await repo.update_status(document_id, "completed")

                logger.info(
                    "Document processed",
                    document_id=str(document_id),
                    chunks=getattr(result, "chunks_created", None),
                    vectors=getattr(result, "vectors_stored", None),
                    duration_ms=getattr(result, "processing_time_ms", None),
                )

            except Exception as e:
                content_type = getattr(document, "content_type", "unknown")
                DOCUMENTS_PROCESSED.labels(status="failed", content_type=content_type).inc()
                await repo.update_status(document_id, "failed", str(e))
                raise

    def _get_uuid(self, payload: dict[str, Any], field: str) -> UUID:
        """Extract and validate UUID field from payload.

        Args:
            payload: Job payload
            field: Field name

        Returns:
            UUID value

        Raises:
            ValueError: If field missing or invalid
        """
        value = payload.get(field)
        if not value:
            raise ValueError(f"Missing required field: {field}")

        if isinstance(value, UUID):
            return value

        try:
            return UUID(str(value))
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid UUID for {field}: {value}") from e

    async def _get_repository(self, session: Any, tenant_id: UUID) -> DocumentRepository:
        """Get document repository.

        Args:
            session: Database session
            tenant_id: Tenant ID

        Returns:
            Document repository
        """
        if self._repository_cls:
            return self._repository_cls(session, tenant_id)

        # Import dynamically to avoid circular imports
        try:
            from aswa_common.db.repositories import DocumentRepository as RepoClass

            return RepoClass(session, tenant_id)
        except ImportError:
            # Fallback for testing or when common lib not available
            raise RuntimeError("DocumentRepository not available")


class BatchDocumentHandler:
    """Handler for batch document processing jobs.

    Processes multiple documents in a single job for efficiency.
    """

    def __init__(
        self,
        session_factory: SessionFactory,
        pipeline: ProcessingPipeline,
    ) -> None:
        """Initialize handler.

        Args:
            session_factory: Factory for creating database sessions
            pipeline: Document processing pipeline
        """
        self.session_factory = session_factory
        self.pipeline = pipeline
        self._single_handler = DocumentProcessingHandler(session_factory, pipeline)

    async def __call__(self, payload: dict[str, Any]) -> None:
        """Process a batch of documents.

        Payload format:
        {
            "documents": [
                {"document_id": "uuid", "tenant_id": "uuid"},
                ...
            ]
        }

        Args:
            payload: Job payload
        """
        documents = payload.get("documents", [])
        if not documents:
            logger.warning("Empty batch payload")
            return

        logger.info("Processing document batch", count=len(documents))

        results = {"success": 0, "failed": 0, "skipped": 0}

        for doc in documents:
            try:
                await self._single_handler(doc)
                results["success"] += 1
            except Exception as e:
                logger.error(
                    "Batch document failed",
                    document_id=doc.get("document_id"),
                    error=str(e),
                )
                results["failed"] += 1

        logger.info("Batch processing complete", **results)


class ReindexHandler:
    """Handler for document reindexing jobs.

    Regenerates embeddings and updates vector store for existing documents.
    """

    def __init__(
        self,
        session_factory: SessionFactory,
        pipeline: ProcessingPipeline,
    ) -> None:
        """Initialize handler.

        Args:
            session_factory: Factory for creating database sessions
            pipeline: Document processing pipeline
        """
        self.session_factory = session_factory
        self.pipeline = pipeline

    async def __call__(self, payload: dict[str, Any]) -> None:
        """Reindex documents.

        Payload format:
        {
            "tenant_id": "uuid",
            "document_ids": ["uuid", ...],  # Optional, all if not specified
            "force": false  # Re-embed even if unchanged
        }

        Args:
            payload: Job payload
        """
        tenant_id = UUID(payload["tenant_id"])
        document_ids = payload.get("document_ids", [])
        force = payload.get("force", False)

        logger.info(
            "Reindexing documents",
            tenant_id=str(tenant_id),
            document_count=len(document_ids) if document_ids else "all",
            force=force,
        )

        # Implementation would:
        # 1. Query documents (filtered by IDs if provided)
        # 2. For each document, regenerate embeddings
        # 3. Update vector store
        # 4. Track progress

        # This is a placeholder - actual implementation depends on
        # specific requirements around chunking strategy changes,
        # embedding model updates, etc.

        logger.info("Reindexing complete", tenant_id=str(tenant_id))
