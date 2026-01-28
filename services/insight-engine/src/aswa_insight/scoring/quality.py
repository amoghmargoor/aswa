from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import structlog

from aswa_insight.models.base import ExtractedInsightBase
from aswa_insight.scoring.confidence import ConfidenceAggregator, ConfidenceScorer

logger = structlog.get_logger()


class QualityLevel(str, Enum):
    """Quality level categories."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    UNUSABLE = "unusable"


@dataclass
class DocumentQuality:
    """Quality assessment of a source document."""
    document_id: str
    text_length: int
    word_count: int
    sentence_count: int
    has_structure: bool  # Has headings, sections, etc.
    language_detected: str = "en"
    readability_score: float = 0.0  # 0-100, Flesch-Kincaid
    noise_ratio: float = 0.0  # Ratio of non-content text

    @property
    def quality_score(self) -> float:
        """Calculate overall quality score (0-1)."""
        score = 0.5  # Base score

        # Length factor
        if self.word_count >= 100:
            score += 0.1
        if self.word_count >= 500:
            score += 0.1

        # Structure bonus
        if self.has_structure:
            score += 0.1

        # Readability (optimal around 60-70)
        if 40 <= self.readability_score <= 80:
            score += 0.1

        # Noise penalty
        score -= self.noise_ratio * 0.2

        return max(0.0, min(1.0, score))

    @property
    def quality_level(self) -> QualityLevel:
        """Get categorical quality level."""
        score = self.quality_score
        if score >= 0.8:
            return QualityLevel.EXCELLENT
        elif score >= 0.6:
            return QualityLevel.GOOD
        elif score >= 0.4:
            return QualityLevel.FAIR
        elif score >= 0.2:
            return QualityLevel.POOR
        else:
            return QualityLevel.UNUSABLE


@dataclass
class ExtractionQuality:
    """Quality assessment of an extraction run."""
    document_id: str
    extraction_type: str
    insight_count: int
    avg_confidence: float
    min_confidence: float
    max_confidence: float
    high_confidence_count: int  # >= 0.8
    low_confidence_count: int  # < 0.4
    has_sources: bool
    processing_time_ms: int
    error_count: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def quality_score(self) -> float:
        """Calculate extraction quality score (0-1)."""
        if self.insight_count == 0:
            return 0.3  # Empty extraction

        score = self.avg_confidence

        # Bonus for having sources
        if self.has_sources:
            score += 0.05

        # Penalty for low confidence extractions
        low_ratio = self.low_confidence_count / self.insight_count
        score -= low_ratio * 0.1

        # Penalty for errors
        score -= min(0.3, self.error_count * 0.1)

        return max(0.0, min(1.0, score))

    @property
    def quality_level(self) -> QualityLevel:
        """Get categorical quality level."""
        score = self.quality_score
        if score >= 0.8:
            return QualityLevel.EXCELLENT
        elif score >= 0.6:
            return QualityLevel.GOOD
        elif score >= 0.4:
            return QualityLevel.FAIR
        elif score >= 0.2:
            return QualityLevel.POOR
        else:
            return QualityLevel.UNUSABLE


class QualityScorer:
    """Score document and extraction quality."""

    def __init__(self):
        self.confidence_scorer = ConfidenceScorer()
        self.confidence_aggregator = ConfidenceAggregator(self.confidence_scorer)

    def assess_document(
        self,
        document_id: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> DocumentQuality:
        """Assess document quality.

        Args:
            document_id: Document identifier
            text: Document text content
            metadata: Optional document metadata

        Returns:
            DocumentQuality assessment
        """
        # Basic text statistics
        text_length = len(text)
        words = text.split()
        word_count = len(words)

        # Simple sentence count (approximate)
        sentence_count = text.count('.') + text.count('!') + text.count('?')
        sentence_count = max(1, sentence_count)

        # Check for structure (headings, bullets, etc.)
        has_structure = any([
            '\n#' in text,  # Markdown headings
            '\n•' in text or '\n-' in text,  # Bullets
            text.count('\n\n') > 3,  # Paragraphs
        ])

        # Simple readability approximation (Flesch-Kincaid-ish)
        avg_word_length = sum(len(w) for w in words) / max(1, word_count)
        avg_sentence_length = word_count / sentence_count
        readability = 206.835 - (1.015 * avg_sentence_length) - (84.6 * (avg_word_length / 5))
        readability = max(0, min(100, readability))

        # Estimate noise ratio (special chars, repeated whitespace, etc.)
        content_chars = sum(1 for c in text if c.isalnum() or c.isspace())
        noise_ratio = 1 - (content_chars / max(1, text_length))

        return DocumentQuality(
            document_id=document_id,
            text_length=text_length,
            word_count=word_count,
            sentence_count=sentence_count,
            has_structure=has_structure,
            readability_score=readability,
            noise_ratio=noise_ratio,
        )

    def assess_extraction(
        self,
        document_id: str,
        extraction_type: str,
        insights: list[ExtractedInsightBase],
        processing_time_ms: int,
        errors: list[str] | None = None,
    ) -> ExtractionQuality:
        """Assess extraction quality.

        Args:
            document_id: Document identifier
            extraction_type: Type of extraction performed
            insights: List of extracted insights
            processing_time_ms: Processing time in milliseconds
            errors: Any errors encountered

        Returns:
            ExtractionQuality assessment
        """
        if not insights:
            return ExtractionQuality(
                document_id=document_id,
                extraction_type=extraction_type,
                insight_count=0,
                avg_confidence=0.0,
                min_confidence=0.0,
                max_confidence=0.0,
                high_confidence_count=0,
                low_confidence_count=0,
                has_sources=False,
                processing_time_ms=processing_time_ms,
                error_count=len(errors) if errors else 0,
            )

        confidences = [i.confidence for i in insights]

        return ExtractionQuality(
            document_id=document_id,
            extraction_type=extraction_type,
            insight_count=len(insights),
            avg_confidence=self.confidence_aggregator.mean(confidences),
            min_confidence=min(confidences),
            max_confidence=max(confidences),
            high_confidence_count=sum(1 for c in confidences if c >= 0.8),
            low_confidence_count=sum(1 for c in confidences if c < 0.4),
            has_sources=any(len(i.sources) > 0 for i in insights),
            processing_time_ms=processing_time_ms,
            error_count=len(errors) if errors else 0,
        )

    def calculate_overall_quality(
        self,
        document_quality: DocumentQuality,
        extraction_qualities: list[ExtractionQuality],
    ) -> float:
        """Calculate overall quality score combining document and extractions.

        Args:
            document_quality: Document quality assessment
            extraction_qualities: List of extraction quality assessments

        Returns:
            Overall quality score (0-1)
        """
        doc_score = document_quality.quality_score

        if not extraction_qualities:
            return doc_score * 0.5  # Penalize if no extractions

        extraction_scores = [eq.quality_score for eq in extraction_qualities]
        avg_extraction_score = self.confidence_aggregator.mean(extraction_scores)

        # Weighted combination: 30% document, 70% extraction
        return (0.3 * doc_score) + (0.7 * avg_extraction_score)
