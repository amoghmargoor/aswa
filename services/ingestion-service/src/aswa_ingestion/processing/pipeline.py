"""End-to-end document processing pipeline."""

import asyncio
import time
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from aswa_common.logging import get_logger

from aswa_ingestion.processing.chunker import TextChunk, TextChunker
from aswa_ingestion.processing.deduplicator import DocumentDeduplicator
from aswa_ingestion.processing.embedder import EmbeddingClient
from aswa_ingestion.processing.parser import DocumentParser

logger = get_logger(__name__)


class VectorStore(Protocol):
    """Protocol for vector store operations."""

    async def upsert(
        self,
        collection: str,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict[str, Any]],
    ) -> None:
        """Insert or update vectors."""
        ...

    async def delete(
        self,
        collection: str,
        ids: list[str],
    ) -> None:
        """Delete vectors by ID."""
        ...


class Document(Protocol):
    """Protocol for document entity."""

    id: UUID
    tenant_id: UUID
    data_source_id: UUID
    title: str
    content: str | None
    content_type: str
    processed_status: str


class ProcessingResult(BaseModel):
    """Result of document processing."""

    document_id: UUID
    success: bool
    chunks_created: int = 0
    vectors_stored: int = 0
    processing_time_ms: int = 0
    error: str | None = None


class DocumentProcessingPipeline:
    """End-to-end document processing pipeline.

    Orchestrates the full document processing workflow:
    1. Parse document content
    2. Check for duplicates
    3. Chunk text
    4. Generate embeddings
    5. Store vectors in Qdrant
    6. Update document status
    """

    def __init__(
        self,
        parser: DocumentParser,
        chunker: TextChunker,
        embedder: EmbeddingClient,
        deduplicator: DocumentDeduplicator,
        vector_store: VectorStore,
        db: AsyncSession,
        collection_name: str = "documents",
    ) -> None:
        """Initialize processing pipeline.

        Args:
            parser: Document parser instance
            chunker: Text chunker instance
            embedder: Embedding client instance
            deduplicator: Deduplicator instance
            vector_store: Vector store client
            db: Database session
            collection_name: Qdrant collection name
        """
        self.parser = parser
        self.chunker = chunker
        self.embedder = embedder
        self.deduplicator = deduplicator
        self.vector_store = vector_store
        self.db = db
        self.collection_name = collection_name

        logger.info("DocumentProcessingPipeline initialized")

    async def process(self, document: Document) -> ProcessingResult:
        """Process a single document through the full pipeline.

        Args:
            document: Document to process

        Returns:
            ProcessingResult with processing details
        """
        start_time = time.time()
        doc_id = document.id

        logger.info(
            f"Processing document: id={doc_id}, "
            f"title={document.title}, content_type={document.content_type}"
        )

        try:
            # Update status to processing
            await self._update_status(doc_id, "processing")

            # Step 1: Parse document
            if document.content is None:
                raise ValueError("Document has no content")

            content_bytes = (
                document.content.encode("utf-8")
                if isinstance(document.content, str)
                else document.content
            )

            parsed = await self.parser.parse(
                content=content_bytes,
                content_type=document.content_type,
                filename=document.title,
            )

            logger.debug(
                f"Parsed document: {len(parsed.elements)} elements, "
                f"{parsed.word_count} words"
            )

            # Step 2: Check for near-duplicates
            dup_result = await self.deduplicator.check_duplicate(
                content=parsed.text,
                tenant_id=document.tenant_id,
                db=self.db,
            )

            if dup_result.is_duplicate and dup_result.duplicate_type == "exact":
                logger.info(f"Skipping exact duplicate of {dup_result.duplicate_id}")
                await self._update_status(
                    doc_id,
                    "duplicate",
                    error=f"Duplicate of {dup_result.duplicate_id}",
                )
                return ProcessingResult(
                    document_id=doc_id,
                    success=False,
                    error=f"Exact duplicate of document {dup_result.duplicate_id}",
                    processing_time_ms=int((time.time() - start_time) * 1000),
                )

            # Step 3: Chunk text
            chunks = self.chunker.chunk_with_metadata(parsed)

            if not chunks:
                logger.warning(f"No chunks generated for document {doc_id}")
                await self._update_status(doc_id, "completed")
                return ProcessingResult(
                    document_id=doc_id,
                    success=True,
                    chunks_created=0,
                    vectors_stored=0,
                    processing_time_ms=int((time.time() - start_time) * 1000),
                )

            logger.debug(f"Created {len(chunks)} chunks")

            # Step 4: Generate embeddings
            chunk_texts = [chunk.content for chunk in chunks]
            embeddings = await self.embedder.embed_batch(chunk_texts)

            logger.debug(f"Generated {len(embeddings)} embeddings")

            # Step 5: Store chunks in database
            chunk_ids = await self._store_chunks(document, chunks)

            # Step 6: Store vectors in Qdrant
            await self._store_vectors(
                document=document,
                chunks=chunks,
                chunk_ids=chunk_ids,
                embeddings=embeddings,
            )

            # Step 7: Add to deduplicator index
            minhash = self.deduplicator.compute_minhash(parsed.text)
            self.deduplicator.add_to_index(str(doc_id), minhash)

            # Update status to completed
            await self._update_status(doc_id, "completed")

            processing_time = int((time.time() - start_time) * 1000)

            logger.info(
                f"Document {doc_id} processed successfully: "
                f"{len(chunks)} chunks, {len(embeddings)} vectors, "
                f"{processing_time}ms"
            )

            return ProcessingResult(
                document_id=doc_id,
                success=True,
                chunks_created=len(chunks),
                vectors_stored=len(embeddings),
                processing_time_ms=processing_time,
            )

        except Exception as e:
            logger.exception(f"Failed to process document {doc_id}: {e}")

            await self._update_status(doc_id, "failed", error=str(e))

            return ProcessingResult(
                document_id=doc_id,
                success=False,
                error=str(e),
                processing_time_ms=int((time.time() - start_time) * 1000),
            )

    async def process_batch(
        self,
        documents: list[Document],
        concurrency: int = 5,
    ) -> list[ProcessingResult]:
        """Process multiple documents concurrently.

        Args:
            documents: Documents to process
            concurrency: Maximum concurrent processing

        Returns:
            List of ProcessingResults
        """
        logger.info(f"Processing batch of {len(documents)} documents")

        semaphore = asyncio.Semaphore(concurrency)

        async def process_with_semaphore(doc: Document) -> ProcessingResult:
            async with semaphore:
                return await self.process(doc)

        results = await asyncio.gather(
            *[process_with_semaphore(doc) for doc in documents],
            return_exceptions=True,
        )

        # Convert exceptions to ProcessingResults
        processed_results: list[ProcessingResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(
                    ProcessingResult(
                        document_id=documents[i].id,
                        success=False,
                        error=str(result),
                    )
                )
            else:
                processed_results.append(result)

        # Log summary
        successful = sum(1 for r in processed_results if r.success)
        logger.info(
            f"Batch processing complete: {successful}/{len(documents)} successful"
        )

        return processed_results

    async def reprocess(self, document_id: UUID) -> ProcessingResult:
        """Delete existing chunks/vectors and reprocess document.

        Args:
            document_id: Document ID to reprocess

        Returns:
            ProcessingResult
        """
        from aswa_common.db.models import Document as DocumentModel, DocumentChunk

        logger.info(f"Reprocessing document {document_id}")

        # Get document
        document = await self.db.get(DocumentModel, document_id)
        if document is None:
            return ProcessingResult(
                document_id=document_id,
                success=False,
                error="Document not found",
            )

        # Delete existing chunks
        stmt = delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        await self.db.execute(stmt)

        # Delete vectors from Qdrant
        chunk_ids = [f"{document_id}_{i}" for i in range(1000)]  # Estimate
        try:
            await self.vector_store.delete(self.collection_name, chunk_ids)
        except Exception as e:
            logger.warning(f"Failed to delete vectors: {e}")

        # Remove from deduplicator index
        self.deduplicator.remove_from_index(str(document_id))

        # Reprocess
        return await self.process(document)

    async def _update_status(
        self,
        doc_id: UUID,
        status: str,
        error: str | None = None,
    ) -> None:
        """Update document processing status.

        Args:
            doc_id: Document ID
            status: New status
            error: Optional error message
        """
        from aswa_common.db.models import Document as DocumentModel
        from datetime import datetime, timezone

        document = await self.db.get(DocumentModel, doc_id)
        if document:
            document.processed_status = status
            if error:
                document.error_message = error
            if status == "completed":
                document.processed_at = datetime.now(timezone.utc)
            await self.db.flush()

    async def _store_chunks(
        self,
        document: Document,
        chunks: list[TextChunk],
    ) -> list[UUID]:
        """Store chunks in database.

        Args:
            document: Parent document
            chunks: Chunks to store

        Returns:
            List of chunk IDs
        """
        from uuid import uuid4
        from aswa_common.db.models import DocumentChunk

        chunk_ids: list[UUID] = []

        for i, chunk in enumerate(chunks):
            chunk_id = uuid4()
            chunk_ids.append(chunk_id)

            db_chunk = DocumentChunk(
                id=chunk_id,
                document_id=document.id,
                tenant_id=document.tenant_id,
                chunk_index=i,
                content=chunk.content,
                token_count=chunk.token_count,
                start_char=chunk.start_char,
                end_char=chunk.end_char,
                metadata=chunk.metadata,
            )
            self.db.add(db_chunk)

        await self.db.flush()

        return chunk_ids

    async def _store_vectors(
        self,
        document: Document,
        chunks: list[TextChunk],
        chunk_ids: list[UUID],
        embeddings: list[list[float]],
    ) -> None:
        """Store vectors in Qdrant.

        Args:
            document: Parent document
            chunks: Text chunks
            chunk_ids: Database chunk IDs
            embeddings: Embedding vectors
        """
        ids = [str(chunk_id) for chunk_id in chunk_ids]

        payloads = [
            {
                "document_id": str(document.id),
                "tenant_id": str(document.tenant_id),
                "data_source_id": str(document.data_source_id),
                "chunk_index": i,
                "text": chunk.content,
                "token_count": chunk.token_count,
                **chunk.metadata,
            }
            for i, chunk in enumerate(chunks)
        ]

        await self.vector_store.upsert(
            collection=self.collection_name,
            ids=ids,
            vectors=embeddings,
            payloads=payloads,
        )
