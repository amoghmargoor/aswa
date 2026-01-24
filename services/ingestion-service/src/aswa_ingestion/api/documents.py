"""Document API endpoints for document upload and processing."""

import hashlib
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from aswa_common.logging import get_logger

from aswa_ingestion.config import settings
from aswa_ingestion.dependencies import DbSession, RedisClient, TenantCtx
from aswa_ingestion.services.document_service import DocumentService

logger = get_logger(__name__)

router = APIRouter()


class DocumentResponse(BaseModel):
    """Document response model."""

    id: UUID
    title: str
    content_type: str
    content_hash: str
    file_size: int
    processed_status: str
    chunk_count: int | None
    created_at: datetime
    processed_at: datetime | None


class DocumentUploadResponse(BaseModel):
    """Response after document upload."""

    document_id: UUID
    title: str
    content_hash: str
    status: str
    is_duplicate: bool
    existing_document_id: UUID | None = None


class ReprocessRequest(BaseModel):
    """Request to reprocess a document."""

    force: bool = Field(
        default=False,
        description="Force reprocessing even if document is already processed",
    )


@router.post("/documents/upload")
async def upload_document(
    tenant_ctx: TenantCtx,
    db: DbSession,
    redis: RedisClient,
    file: UploadFile = File(...),
    data_source_id: UUID = Form(...),
    title: str | None = Form(None),
    external_id: str | None = Form(None),
) -> DocumentUploadResponse:
    """Upload a document for processing.

    The document will be:
    1. Validated for size and content type
    2. Checked for duplicates by content hash
    3. Stored in blob storage
    4. Queued for processing (chunking, embedding)

    Args:
        tenant_ctx: Tenant context
        db: Database session
        redis: Redis client
        file: Uploaded file
        data_source_id: Associated data source ID
        title: Optional document title (defaults to filename)
        external_id: Optional external ID for deduplication

    Returns:
        Upload result with document ID
    """
    logger.info(
        f"Document upload: filename={file.filename}, "
        f"content_type={file.content_type}, data_source={data_source_id}"
    )

    # Validate content type
    if file.content_type not in settings.ingestion.supported_content_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported content type: {file.content_type}. "
            f"Supported: {settings.ingestion.supported_content_types}",
        )

    # Read file content
    content = await file.read()
    file_size = len(content)

    # Validate file size
    max_size = settings.ingestion.max_file_size_mb * 1024 * 1024
    if file_size > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large: {file_size} bytes. Maximum: {max_size} bytes",
        )

    # Calculate content hash
    content_hash = hashlib.sha256(content).hexdigest()

    doc_service = DocumentService(db, redis)

    # Check for duplicates
    existing_doc = await doc_service.check_duplicate(
        content_hash=content_hash,
        tenant_id=tenant_ctx.tenant_id,
    )

    if existing_doc:
        logger.info(f"Duplicate document detected: {existing_doc.id}")
        return DocumentUploadResponse(
            document_id=existing_doc.id,
            title=existing_doc.title,
            content_hash=content_hash,
            status="duplicate",
            is_duplicate=True,
            existing_document_id=existing_doc.id,
        )

    # Store document
    doc_title = title or file.filename or "Untitled Document"

    document = await doc_service.store_document(
        tenant_id=tenant_ctx.tenant_id,
        data_source_id=data_source_id,
        external_id=external_id or f"upload-{content_hash[:16]}",
        title=doc_title,
        content=content,
        content_type=file.content_type or "application/octet-stream",
        content_hash=content_hash,
        file_size=file_size,
        metadata={"original_filename": file.filename},
    )

    # Queue for processing
    await doc_service.queue_for_processing(document.id)

    logger.info(f"Document uploaded successfully: {document.id}")

    return DocumentUploadResponse(
        document_id=document.id,
        title=doc_title,
        content_hash=content_hash,
        status="pending",
        is_duplicate=False,
    )


@router.get("/documents/{doc_id}")
async def get_document(
    doc_id: UUID,
    tenant_ctx: TenantCtx,
    db: DbSession,
) -> DocumentResponse:
    """Get document details by ID.

    Args:
        doc_id: Document ID
        tenant_ctx: Tenant context
        db: Database session

    Returns:
        Document details
    """
    logger.debug(f"Getting document {doc_id}")

    doc_service = DocumentService(db, None)
    document = await doc_service.get_document(doc_id, tenant_ctx.tenant_id)

    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    return DocumentResponse(
        id=document.id,
        title=document.title,
        content_type=document.content_type,
        content_hash=document.content_hash,
        file_size=document.file_size,
        processed_status=document.processed_status,
        chunk_count=document.chunk_count if hasattr(document, "chunk_count") else None,
        created_at=document.created_at,
        processed_at=document.processed_at,
    )


@router.post("/documents/{doc_id}/reprocess")
async def reprocess_document(
    doc_id: UUID,
    request: ReprocessRequest,
    tenant_ctx: TenantCtx,
    db: DbSession,
    redis: RedisClient,
) -> dict[str, Any]:
    """Reprocess a document.

    This will:
    1. Delete existing chunks and embeddings
    2. Re-extract text and create new chunks
    3. Generate new embeddings

    Args:
        doc_id: Document ID to reprocess
        request: Reprocess options
        tenant_ctx: Tenant context
        db: Database session
        redis: Redis client

    Returns:
        Confirmation message
    """
    logger.info(f"Reprocessing document {doc_id}, force={request.force}")

    doc_service = DocumentService(db, redis)
    document = await doc_service.get_document(doc_id, tenant_ctx.tenant_id)

    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    if document.processed_status == "processing" and not request.force:
        raise HTTPException(
            status_code=409,
            detail="Document is currently being processed. Use force=true to reprocess anyway.",
        )

    # Reset status and queue for processing
    await doc_service.reset_for_reprocessing(doc_id)
    await doc_service.queue_for_processing(doc_id)

    return {
        "message": f"Document {doc_id} queued for reprocessing",
        "document_id": str(doc_id),
        "status": "pending",
    }


@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: UUID,
    tenant_ctx: TenantCtx,
    db: DbSession,
    redis: RedisClient,
) -> dict[str, str]:
    """Delete a document and all associated data.

    This will:
    1. Delete document chunks from database
    2. Delete embeddings from vector store
    3. Delete blob from storage
    4. Delete document record

    Args:
        doc_id: Document ID to delete
        tenant_ctx: Tenant context
        db: Database session
        redis: Redis client

    Returns:
        Confirmation message
    """
    logger.info(f"Deleting document {doc_id}")

    doc_service = DocumentService(db, redis)
    document = await doc_service.get_document(doc_id, tenant_ctx.tenant_id)

    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    await doc_service.delete_document(doc_id)

    logger.info(f"Document {doc_id} deleted successfully")

    return {"message": f"Document {doc_id} deleted successfully"}


@router.get("/documents/{doc_id}/chunks")
async def get_document_chunks(
    doc_id: UUID,
    tenant_ctx: TenantCtx,
    db: DbSession,
) -> list[dict[str, Any]]:
    """Get all chunks for a document.

    Args:
        doc_id: Document ID
        tenant_ctx: Tenant context
        db: Database session

    Returns:
        List of document chunks
    """
    logger.debug(f"Getting chunks for document {doc_id}")

    doc_service = DocumentService(db, None)

    # Verify document exists and belongs to tenant
    document = await doc_service.get_document(doc_id, tenant_ctx.tenant_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    chunks = await doc_service.get_chunks(doc_id)

    return [
        {
            "id": str(chunk.id),
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "vector_id": chunk.vector_id,
            "metadata": chunk.chunk_metadata,
            "created_at": chunk.created_at.isoformat() if chunk.created_at else None,
        }
        for chunk in chunks
    ]
