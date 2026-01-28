"""Document processing flows.

Provides Prefect flows for processing documents through the ingestion
pipeline: parsing, chunking, embedding, and storing in vector database.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

import structlog
from prefect import flow, get_run_logger, task
from prefect.concurrency.asyncio import concurrency

from aswa_ingestion.config import settings

logger = structlog.get_logger()


# Global pipeline instance (initialized on first use)
_pipeline_instance: Any = None


async def get_processing_pipeline() -> Any:
    """Get or create the document processing pipeline.

    Returns:
        DocumentProcessingPipeline instance
    """
    global _pipeline_instance

    if _pipeline_instance is None:
        try:
            from aswa_ingestion.processing.pipeline import DocumentProcessingPipeline
            from aswa_ingestion.processing.embedder import EmbeddingClient
            from aswa_ingestion.vectorstore.qdrant import QdrantVectorStore

            # Initialize components
            embedder = EmbeddingClient()
            vector_store = QdrantVectorStore()
            await vector_store.initialize()

            _pipeline_instance = DocumentProcessingPipeline(
                embedder=embedder,
                vector_store=vector_store,
            )
        except ImportError:
            # Return mock for testing
            logger.warning("Using mock pipeline")
            _pipeline_instance = MockPipeline()

    return _pipeline_instance


class MockPipeline:
    """Mock pipeline for testing."""

    async def process(self, document: Any) -> Any:
        """Mock process method."""
        from dataclasses import dataclass

        @dataclass
        class Result:
            chunks_created: int = 10
            vectors_stored: int = 10
            processing_time_ms: int = 100

        return Result()


@task(name="fetch_pending_documents")
async def fetch_pending_documents(
    tenant_id: UUID | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Fetch documents pending processing.

    Args:
        tenant_id: Optional tenant filter
        limit: Maximum documents to fetch

    Returns:
        List of document dicts
    """
    from aswa_common.db import get_async_session
    from sqlalchemy import select
    from aswa_common.db.models import Document

    async with get_async_session() as session:
        stmt = (
            select(Document)
            .where(Document.processed_status.in_(["pending", "failed"]))
            .order_by(Document.created_at.asc())
            .limit(limit)
        )

        if tenant_id:
            stmt = stmt.where(Document.tenant_id == tenant_id)

        result = await session.execute(stmt)
        docs = result.scalars().all()

        return [
            {
                "id": str(doc.id),
                "tenant_id": str(doc.tenant_id),
                "content_type": doc.content_type,
                "title": doc.title,
                "blob_path": doc.blob_path,
                "processed_status": doc.processed_status,
            }
            for doc in docs
        ]


@task(
    name="process_single_document",
    retries=2,
    retry_delay_seconds=30,
)
async def process_single_document(document: dict[str, Any]) -> dict[str, Any]:
    """Process a single document through the pipeline.

    Args:
        document: Document dict with id, tenant_id, etc.

    Returns:
        Processing result dict
    """
    from aswa_common.db import get_async_session
    from sqlalchemy import select, update
    from aswa_common.db.models import Document

    prefect_logger = get_run_logger()
    doc_id = UUID(document["id"])
    tenant_id = UUID(document["tenant_id"])

    async with get_async_session() as session:
        # Fetch full document
        stmt = select(Document).where(Document.id == doc_id)
        result = await session.execute(stmt)
        doc = result.scalar_one_or_none()

        if not doc:
            return {"id": document["id"], "status": "not_found"}

        # Update status to processing
        update_stmt = (
            update(Document)
            .where(Document.id == doc_id)
            .values(processed_status="processing", processed_at=datetime.utcnow())
        )
        await session.execute(update_stmt)
        await session.commit()

        try:
            # Get pipeline and process
            pipeline = await get_processing_pipeline()
            start_time = datetime.utcnow()
            result = await pipeline.process(doc)
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            # Update status to completed
            update_stmt = (
                update(Document)
                .where(Document.id == doc_id)
                .values(
                    processed_status="completed",
                    processed_at=datetime.utcnow(),
                    chunk_count=getattr(result, "chunks_created", 0),
                )
            )
            await session.execute(update_stmt)
            await session.commit()

            prefect_logger.info(
                f"Processed document {doc_id}: "
                f"{getattr(result, 'chunks_created', 0)} chunks, "
                f"{processing_time:.0f}ms"
            )

            return {
                "id": document["id"],
                "status": "success",
                "chunks_created": getattr(result, "chunks_created", 0),
                "vectors_stored": getattr(result, "vectors_stored", 0),
                "processing_time_ms": processing_time,
            }

        except Exception as e:
            prefect_logger.error(f"Processing failed for {doc_id}: {e}")

            # Update status to failed
            update_stmt = (
                update(Document)
                .where(Document.id == doc_id)
                .values(
                    processed_status="failed",
                    error_message=str(e),
                    processed_at=datetime.utcnow(),
                )
            )
            await session.execute(update_stmt)
            await session.commit()

            return {
                "id": document["id"],
                "status": "failed",
                "error": str(e),
            }


@task(name="aggregate_processing_stats")
def aggregate_processing_stats(
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate processing results into summary stats.

    Args:
        results: List of individual processing results

    Returns:
        Aggregated statistics
    """
    stats = {
        "total": len(results),
        "success": 0,
        "failed": 0,
        "not_found": 0,
        "total_chunks": 0,
        "total_vectors": 0,
        "avg_processing_time_ms": 0,
    }

    processing_times = []

    for result in results:
        status = result.get("status", "unknown")
        if status == "success":
            stats["success"] += 1
            stats["total_chunks"] += result.get("chunks_created", 0)
            stats["total_vectors"] += result.get("vectors_stored", 0)
            if result.get("processing_time_ms"):
                processing_times.append(result["processing_time_ms"])
        elif status == "failed":
            stats["failed"] += 1
        elif status == "not_found":
            stats["not_found"] += 1

    if processing_times:
        stats["avg_processing_time_ms"] = sum(processing_times) / len(processing_times)

    return stats


@flow(
    name="process_pending_documents",
    description="Process all pending documents through the ingestion pipeline",
)
async def process_pending_documents(
    tenant_id: UUID | None = None,
    batch_size: int = 50,
    max_concurrent: int = 10,
    max_documents: int | None = None,
) -> dict[str, Any]:
    """Flow to process pending documents.

    Fetches pending documents and processes them through the
    ingestion pipeline with configurable concurrency.

    Args:
        tenant_id: Optional tenant filter
        batch_size: Documents per batch
        max_concurrent: Maximum concurrent processing tasks
        max_documents: Maximum total documents to process

    Returns:
        Processing statistics
    """
    prefect_logger = get_run_logger()
    prefect_logger.info(
        f"Starting document processing, tenant={tenant_id}, "
        f"batch_size={batch_size}, max_concurrent={max_concurrent}"
    )

    all_results: list[dict[str, Any]] = []
    documents_processed = 0

    while True:
        # Check limit
        if max_documents and documents_processed >= max_documents:
            prefect_logger.info(f"Reached max documents limit: {max_documents}")
            break

        # Calculate remaining limit
        remaining = batch_size
        if max_documents:
            remaining = min(batch_size, max_documents - documents_processed)

        # Fetch batch of pending documents
        pending = await fetch_pending_documents(tenant_id, remaining)

        if not pending:
            prefect_logger.info("No more pending documents")
            break

        prefect_logger.info(f"Processing batch of {len(pending)} documents")

        # Process with concurrency limit
        async with concurrency("document-processing", max_concurrent):
            # Process documents concurrently
            results = []
            for doc in pending:
                result = await process_single_document(doc)
                results.append(result)

        all_results.extend(results)
        documents_processed += len(pending)

        # Log batch progress
        batch_stats = aggregate_processing_stats(results)
        prefect_logger.info(
            f"Batch completed: {batch_stats['success']} success, "
            f"{batch_stats['failed']} failed"
        )

    # Aggregate final stats
    final_stats = aggregate_processing_stats(all_results)
    prefect_logger.info(f"Processing completed: {final_stats}")

    return final_stats


@flow(
    name="reprocess_failed_documents",
    description="Reprocess documents that previously failed",
)
async def reprocess_failed_documents(
    tenant_id: UUID | None = None,
    max_attempts: int = 3,
    limit: int = 100,
) -> dict[str, Any]:
    """Flow to reprocess failed documents.

    Fetches documents with failed status and attempts to reprocess them.

    Args:
        tenant_id: Optional tenant filter
        max_attempts: Maximum retry attempts to consider
        limit: Maximum documents to reprocess

    Returns:
        Reprocessing statistics
    """
    from aswa_common.db import get_async_session
    from sqlalchemy import select, update
    from aswa_common.db.models import Document

    prefect_logger = get_run_logger()
    prefect_logger.info(f"Starting reprocessing of failed documents, tenant={tenant_id}")

    async with get_async_session() as session:
        stmt = (
            select(Document)
            .where(Document.processed_status == "failed")
            .limit(limit)
        )

        if tenant_id:
            stmt = stmt.where(Document.tenant_id == tenant_id)

        result = await session.execute(stmt)
        failed_docs = result.scalars().all()

        # Reset status to pending for reprocessing
        doc_ids = [doc.id for doc in failed_docs]
        if doc_ids:
            update_stmt = (
                update(Document)
                .where(Document.id.in_(doc_ids))
                .values(processed_status="pending", error_message=None)
            )
            await session.execute(update_stmt)
            await session.commit()

    if not doc_ids:
        prefect_logger.info("No failed documents to reprocess")
        return {"total": 0, "reset": 0}

    prefect_logger.info(f"Reset {len(doc_ids)} documents for reprocessing")

    # Now process them
    stats = await process_pending_documents(tenant_id=tenant_id, max_documents=len(doc_ids))
    stats["reset_count"] = len(doc_ids)

    return stats
