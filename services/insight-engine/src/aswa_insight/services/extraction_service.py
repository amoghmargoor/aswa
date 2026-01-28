"""Extraction service for LLM-based insight extraction."""

import asyncio
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import structlog
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from aswa_insight.config import settings
from aswa_insight.llm.client import LLMClient

logger = structlog.get_logger()


# Pydantic models for structured extraction

class ExtractedEntity(BaseModel):
    """An extracted entity from document."""

    name: str = Field(description="Entity name")
    entity_type: str = Field(description="Type: person, organization, location, product, etc.")
    description: str = Field(description="Brief description")
    confidence: float = Field(ge=0, le=1, description="Extraction confidence")
    mentions: list[str] = Field(default_factory=list, description="Text excerpts where mentioned")


class ExtractedRisk(BaseModel):
    """An extracted risk from document."""

    title: str = Field(description="Risk title")
    description: str = Field(description="Risk description")
    category: str = Field(description="Risk category: financial, operational, security, etc.")
    severity: str = Field(description="Severity: low, medium, high, critical")
    likelihood: str = Field(description="Likelihood: unlikely, possible, likely, certain")
    mitigation: str | None = Field(default=None, description="Suggested mitigation")
    confidence: float = Field(ge=0, le=1, description="Extraction confidence")
    evidence: list[str] = Field(default_factory=list, description="Supporting evidence")


class ExtractedOpportunity(BaseModel):
    """An extracted opportunity from document."""

    title: str = Field(description="Opportunity title")
    description: str = Field(description="Opportunity description")
    category: str = Field(description="Category: growth, efficiency, innovation, etc.")
    impact: str = Field(description="Impact: low, medium, high")
    effort: str = Field(description="Implementation effort: low, medium, high")
    confidence: float = Field(ge=0, le=1, description="Extraction confidence")
    evidence: list[str] = Field(default_factory=list, description="Supporting evidence")


class ExtractedPattern(BaseModel):
    """An extracted pattern from document."""

    title: str = Field(description="Pattern title")
    description: str = Field(description="Pattern description")
    pattern_type: str = Field(description="Type: trend, anomaly, correlation, etc.")
    frequency: str = Field(description="How often observed")
    confidence: float = Field(ge=0, le=1, description="Extraction confidence")
    evidence: list[str] = Field(default_factory=list, description="Supporting evidence")


class DocumentExtractionResult(BaseModel):
    """Complete extraction result for a document."""

    entities: list[ExtractedEntity] = Field(default_factory=list)
    risks: list[ExtractedRisk] = Field(default_factory=list)
    opportunities: list[ExtractedOpportunity] = Field(default_factory=list)
    patterns: list[ExtractedPattern] = Field(default_factory=list)


class ExtractionJob(BaseModel):
    """Extraction job model."""

    id: UUID
    tenant_id: UUID
    status: str  # queued, processing, completed, failed, cancelled
    document_ids: list[UUID]
    extraction_types: list[str]
    force_reextract: bool
    priority: int
    total_documents: int
    processed_documents: int
    successful_extractions: int
    failed_extractions: int
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None


class ExtractionService:
    """Service for extracting insights from documents using LLM."""

    SYSTEM_PROMPT = """You are an expert analyst extracting structured insights from documents.
Analyze the provided text and extract the requested information types.
Be precise and only extract information that is clearly present in the text.
Assign confidence scores based on how certain you are about each extraction.
Include specific text excerpts as evidence for your extractions."""

    ENTITY_PROMPT = """Extract all entities from the following text.
Focus on: people, organizations, locations, products, technologies, and concepts.

Text:
{text}

Extract entities with their type, description, and confidence score."""

    RISK_PROMPT = """Analyze the following text and identify any risks mentioned or implied.
Consider: financial, operational, security, compliance, and strategic risks.

Text:
{text}

Extract risks with severity, likelihood, and potential mitigations."""

    OPPORTUNITY_PROMPT = """Analyze the following text and identify opportunities.
Consider: growth opportunities, efficiency improvements, innovation potential.

Text:
{text}

Extract opportunities with impact assessment and implementation effort."""

    PATTERN_PROMPT = """Analyze the following text for patterns, trends, or anomalies.

Text:
{text}

Extract patterns with their type, frequency, and supporting evidence."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        llm_client: LLMClient,
    ) -> None:
        """Initialize extraction service.

        Args:
            session_factory: Database session factory
            llm_client: LLM client for extraction
        """
        self.session_factory = session_factory
        self.llm_client = llm_client
        self._jobs: dict[UUID, ExtractionJob] = {}  # In-memory storage for demo

    async def create_extraction_job(
        self,
        document_ids: list[UUID],
        tenant_id: UUID,
        extraction_types: list[str],
        force_reextract: bool = False,
        priority: int = 0,
    ) -> ExtractionJob:
        """Create a new extraction job.

        Args:
            document_ids: Documents to process
            tenant_id: Tenant ID
            extraction_types: Types of insights to extract
            force_reextract: Force re-extraction
            priority: Job priority

        Returns:
            Created job
        """
        job = ExtractionJob(
            id=uuid4(),
            tenant_id=tenant_id,
            status="queued",
            document_ids=document_ids,
            extraction_types=extraction_types,
            force_reextract=force_reextract,
            priority=priority,
            total_documents=len(document_ids),
            processed_documents=0,
            successful_extractions=0,
            failed_extractions=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        self._jobs[job.id] = job

        logger.info(
            "Created extraction job",
            job_id=str(job.id),
            documents=len(document_ids),
            types=extraction_types,
        )

        return job

    async def run_extraction_job(self, job_id: UUID, tenant_id: UUID) -> None:
        """Run an extraction job.

        Args:
            job_id: Job ID
            tenant_id: Tenant ID
        """
        job = self._jobs.get(job_id)
        if not job or job.tenant_id != tenant_id:
            logger.warning("Job not found", job_id=str(job_id))
            return

        job.status = "processing"
        job.updated_at = datetime.utcnow()

        logger.info("Starting extraction job", job_id=str(job_id))

        try:
            # Process documents with concurrency limit
            semaphore = asyncio.Semaphore(settings.insight.concurrent_extractions)

            async def process_with_semaphore(doc_id: UUID) -> bool:
                async with semaphore:
                    return await self._process_document(doc_id, tenant_id, job)

            tasks = [process_with_semaphore(doc_id) for doc_id in job.document_ids]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                job.processed_documents += 1
                if isinstance(result, Exception):
                    job.failed_extractions += 1
                elif result:
                    job.successful_extractions += 1
                else:
                    job.failed_extractions += 1

            job.status = "completed"
            job.completed_at = datetime.utcnow()

            logger.info(
                "Extraction job completed",
                job_id=str(job_id),
                success=job.successful_extractions,
                failed=job.failed_extractions,
            )

        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)
            logger.error("Extraction job failed", job_id=str(job_id), error=str(e))

        finally:
            job.updated_at = datetime.utcnow()

    async def _process_document(
        self,
        document_id: UUID,
        tenant_id: UUID,
        job: ExtractionJob,
    ) -> bool:
        """Process a single document.

        Args:
            document_id: Document ID
            tenant_id: Tenant ID
            job: Extraction job

        Returns:
            True if successful
        """
        logger.debug("Processing document", document_id=str(document_id))

        try:
            # Fetch document content (mock for now)
            document_text = await self._fetch_document_content(document_id, tenant_id)

            if not document_text:
                logger.warning("No content for document", document_id=str(document_id))
                return False

            # Extract based on requested types
            result = DocumentExtractionResult()

            if "entities" in job.extraction_types:
                result.entities = await self._extract_entities(document_text)

            if "risks" in job.extraction_types:
                result.risks = await self._extract_risks(document_text)

            if "opportunities" in job.extraction_types:
                result.opportunities = await self._extract_opportunities(document_text)

            if "patterns" in job.extraction_types:
                result.patterns = await self._extract_patterns(document_text)

            # Store insights
            await self._store_insights(document_id, tenant_id, result)

            logger.info(
                "Document processed",
                document_id=str(document_id),
                entities=len(result.entities),
                risks=len(result.risks),
                opportunities=len(result.opportunities),
            )

            return True

        except Exception as e:
            logger.error(
                "Document processing failed",
                document_id=str(document_id),
                error=str(e),
            )
            return False

    async def _fetch_document_content(
        self, document_id: UUID, tenant_id: UUID
    ) -> str | None:
        """Fetch document content from database.

        Args:
            document_id: Document ID
            tenant_id: Tenant ID

        Returns:
            Document text content
        """
        # In production, this would fetch from database/blob storage
        # For now, return mock content
        return "This is sample document content for testing extraction."

    async def _extract_entities(self, text: str) -> list[ExtractedEntity]:
        """Extract entities from text.

        Args:
            text: Document text

        Returns:
            Extracted entities
        """
        try:
            class EntityResponse(BaseModel):
                entities: list[ExtractedEntity]

            prompt = self.ENTITY_PROMPT.format(text=text[:10000])
            response = await self.llm_client.extract_structured(
                prompt=prompt,
                response_model=EntityResponse,
                system_prompt=self.SYSTEM_PROMPT,
            )
            return response.entities
        except Exception as e:
            logger.error("Entity extraction failed", error=str(e))
            return []

    async def _extract_risks(self, text: str) -> list[ExtractedRisk]:
        """Extract risks from text."""
        try:
            class RiskResponse(BaseModel):
                risks: list[ExtractedRisk]

            prompt = self.RISK_PROMPT.format(text=text[:10000])
            response = await self.llm_client.extract_structured(
                prompt=prompt,
                response_model=RiskResponse,
                system_prompt=self.SYSTEM_PROMPT,
            )
            return response.risks
        except Exception as e:
            logger.error("Risk extraction failed", error=str(e))
            return []

    async def _extract_opportunities(self, text: str) -> list[ExtractedOpportunity]:
        """Extract opportunities from text."""
        try:
            class OpportunityResponse(BaseModel):
                opportunities: list[ExtractedOpportunity]

            prompt = self.OPPORTUNITY_PROMPT.format(text=text[:10000])
            response = await self.llm_client.extract_structured(
                prompt=prompt,
                response_model=OpportunityResponse,
                system_prompt=self.SYSTEM_PROMPT,
            )
            return response.opportunities
        except Exception as e:
            logger.error("Opportunity extraction failed", error=str(e))
            return []

    async def _extract_patterns(self, text: str) -> list[ExtractedPattern]:
        """Extract patterns from text."""
        try:
            class PatternResponse(BaseModel):
                patterns: list[ExtractedPattern]

            prompt = self.PATTERN_PROMPT.format(text=text[:10000])
            response = await self.llm_client.extract_structured(
                prompt=prompt,
                response_model=PatternResponse,
                system_prompt=self.SYSTEM_PROMPT,
            )
            return response.patterns
        except Exception as e:
            logger.error("Pattern extraction failed", error=str(e))
            return []

    async def _store_insights(
        self,
        document_id: UUID,
        tenant_id: UUID,
        result: DocumentExtractionResult,
    ) -> None:
        """Store extracted insights in database.

        Args:
            document_id: Source document ID
            tenant_id: Tenant ID
            result: Extraction result
        """
        # In production, this would store in database
        # For now, just log
        logger.info(
            "Storing insights",
            document_id=str(document_id),
            entities=len(result.entities),
            risks=len(result.risks),
            opportunities=len(result.opportunities),
            patterns=len(result.patterns),
        )

    async def get_job_status(
        self, job_id: UUID, tenant_id: UUID
    ) -> dict[str, Any] | None:
        """Get job status.

        Args:
            job_id: Job ID
            tenant_id: Tenant ID

        Returns:
            Job status dict or None
        """
        job = self._jobs.get(job_id)
        if not job or job.tenant_id != tenant_id:
            return None

        progress = 0.0
        if job.total_documents > 0:
            progress = (job.processed_documents / job.total_documents) * 100

        return {
            "job_id": job.id,
            "status": job.status,
            "total_documents": job.total_documents,
            "processed_documents": job.processed_documents,
            "successful_extractions": job.successful_extractions,
            "failed_extractions": job.failed_extractions,
            "progress_percent": progress,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "error_message": job.error_message,
        }

    async def get_job_results(
        self, job_id: UUID, tenant_id: UUID
    ) -> list[dict[str, Any]] | None:
        """Get job results.

        Args:
            job_id: Job ID
            tenant_id: Tenant ID

        Returns:
            List of extraction results or None
        """
        job = self._jobs.get(job_id)
        if not job or job.tenant_id != tenant_id:
            return None

        # In production, fetch from database
        return []

    async def cancel_job(self, job_id: UUID, tenant_id: UUID) -> bool:
        """Cancel a job.

        Args:
            job_id: Job ID
            tenant_id: Tenant ID

        Returns:
            True if cancelled
        """
        job = self._jobs.get(job_id)
        if not job or job.tenant_id != tenant_id:
            return False

        if job.status in ("completed", "failed", "cancelled"):
            return False

        job.status = "cancelled"
        job.updated_at = datetime.utcnow()

        logger.info("Job cancelled", job_id=str(job_id))
        return True
