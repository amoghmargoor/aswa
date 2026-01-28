# Task 3.2.3: Confidence Scoring Logic

## Context

You are working on the ASWA insight-engine service at `/services/insight-engine/`. The extraction models (Task 3.2.1) and prompt templates (Task 3.2.2) have been created. Each extracted insight has a `confidence` score from 0.0 to 1.0.

This task implements the confidence scoring logic to:
1. Validate and normalize LLM-provided confidence scores
2. Apply adjustments based on extraction context
3. Aggregate confidence across multiple extractions
4. Calculate overall document/insight quality scores

## Objective

Create a robust confidence scoring system that produces reliable, calibrated confidence scores for extracted insights.

## Requirements

### 1. Create `/services/insight-engine/src/aswa_insight/scoring/__init__.py`
```python
from .confidence import (
    ConfidenceScorer,
    ConfidenceAdjuster,
    ConfidenceAggregator,
    calculate_risk_score,
    calibrate_confidence,
)
from .quality import QualityScorer, DocumentQuality, ExtractionQuality

__all__ = [
    "ConfidenceScorer",
    "ConfidenceAdjuster",
    "ConfidenceAggregator",
    "QualityScorer",
    "DocumentQuality",
    "ExtractionQuality",
    "calculate_risk_score",
    "calibrate_confidence",
]
```

### 2. Create `/services/insight-engine/src/aswa_insight/scoring/confidence.py`
Core confidence scoring logic:

```python
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable
import structlog
from pydantic import BaseModel, Field

from aswa_insight.models.base import ConfidenceLevel, ExtractedInsightBase
from aswa_insight.models.risks import Severity, Likelihood

logger = structlog.get_logger()


class AdjustmentReason(str, Enum):
    """Reasons for confidence adjustment."""
    SOURCE_QUALITY = "source_quality"
    EXTRACTION_COUNT = "extraction_count"
    CROSS_VALIDATION = "cross_validation"
    TEMPORAL_DECAY = "temporal_decay"
    USER_FEEDBACK = "user_feedback"
    ENTITY_DENSITY = "entity_density"
    TEXT_LENGTH = "text_length"
    AMBIGUITY = "ambiguity"


@dataclass
class ConfidenceAdjustment:
    """A confidence score adjustment."""
    reason: AdjustmentReason
    factor: float  # Multiplicative factor
    description: str


class ConfidenceScorer:
    """Score and validate confidence values."""

    def __init__(
        self,
        min_confidence: float = 0.0,
        max_confidence: float = 1.0,
        default_confidence: float = 0.5,
    ):
        self.min_confidence = min_confidence
        self.max_confidence = max_confidence
        self.default_confidence = default_confidence

    def validate(self, confidence: float | None) -> float:
        """Validate and clamp confidence score."""
        if confidence is None:
            return self.default_confidence

        # Clamp to valid range
        return max(self.min_confidence, min(self.max_confidence, confidence))

    def to_level(self, confidence: float) -> ConfidenceLevel:
        """Convert numeric confidence to categorical level."""
        validated = self.validate(confidence)

        if validated >= 0.8:
            return ConfidenceLevel.VERY_HIGH
        elif validated >= 0.6:
            return ConfidenceLevel.HIGH
        elif validated >= 0.4:
            return ConfidenceLevel.MEDIUM
        elif validated >= 0.2:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW

    def from_level(self, level: ConfidenceLevel) -> float:
        """Convert categorical level to numeric confidence (midpoint)."""
        mapping = {
            ConfidenceLevel.VERY_HIGH: 0.9,
            ConfidenceLevel.HIGH: 0.7,
            ConfidenceLevel.MEDIUM: 0.5,
            ConfidenceLevel.LOW: 0.3,
            ConfidenceLevel.VERY_LOW: 0.1,
        }
        return mapping.get(level, self.default_confidence)


class ConfidenceAdjuster:
    """Apply contextual adjustments to confidence scores."""

    def __init__(self, scorer: ConfidenceScorer | None = None):
        self.scorer = scorer or ConfidenceScorer()
        self._adjustment_history: list[ConfidenceAdjustment] = []

    def adjust(
        self,
        confidence: float,
        adjustments: list[ConfidenceAdjustment],
    ) -> tuple[float, list[ConfidenceAdjustment]]:
        """Apply adjustments to confidence score.

        Args:
            confidence: Base confidence score
            adjustments: List of adjustments to apply

        Returns:
            Tuple of (adjusted_confidence, applied_adjustments)
        """
        validated = self.scorer.validate(confidence)
        result = validated

        applied = []
        for adj in adjustments:
            # Apply multiplicative factor
            result = result * adj.factor
            applied.append(adj)

            logger.debug(
                "Applied confidence adjustment",
                reason=adj.reason,
                factor=adj.factor,
                before=validated,
                after=result,
            )

        # Clamp final result
        result = self.scorer.validate(result)

        return result, applied

    def adjust_for_source_quality(
        self,
        confidence: float,
        source_reliability: float,  # 0-1
    ) -> float:
        """Adjust based on source document quality."""
        factor = 0.5 + (0.5 * source_reliability)  # Range: 0.5 to 1.0
        adjustment = ConfidenceAdjustment(
            reason=AdjustmentReason.SOURCE_QUALITY,
            factor=factor,
            description=f"Source reliability: {source_reliability:.2f}",
        )
        adjusted, _ = self.adjust(confidence, [adjustment])
        return adjusted

    def adjust_for_text_length(
        self,
        confidence: float,
        text_length: int,
        min_optimal: int = 100,
        max_optimal: int = 10000,
    ) -> float:
        """Adjust based on text length (very short or long texts are less reliable)."""
        if text_length < min_optimal:
            # Penalize very short texts
            factor = max(0.7, text_length / min_optimal)
        elif text_length > max_optimal:
            # Slight penalty for very long texts (may miss details)
            factor = max(0.9, 1.0 - (text_length - max_optimal) / (max_optimal * 10))
        else:
            factor = 1.0

        adjustment = ConfidenceAdjustment(
            reason=AdjustmentReason.TEXT_LENGTH,
            factor=factor,
            description=f"Text length: {text_length} chars",
        )
        adjusted, _ = self.adjust(confidence, [adjustment])
        return adjusted

    def adjust_for_extraction_count(
        self,
        confidence: float,
        extraction_count: int,
        expected_min: int = 1,
        expected_max: int = 50,
    ) -> float:
        """Adjust based on number of extractions (suspicious if too few or too many)."""
        if extraction_count < expected_min:
            factor = 0.8  # Might have missed things
        elif extraction_count > expected_max:
            factor = 0.9  # Might have over-extracted
        else:
            factor = 1.0

        adjustment = ConfidenceAdjustment(
            reason=AdjustmentReason.EXTRACTION_COUNT,
            factor=factor,
            description=f"Extraction count: {extraction_count}",
        )
        adjusted, _ = self.adjust(confidence, [adjustment])
        return adjusted

    def adjust_for_user_feedback(
        self,
        confidence: float,
        positive_feedback_count: int,
        negative_feedback_count: int,
    ) -> float:
        """Adjust based on user feedback history."""
        total = positive_feedback_count + negative_feedback_count
        if total == 0:
            return confidence

        positive_ratio = positive_feedback_count / total

        # Adjust towards user validation
        if positive_ratio > 0.7:
            factor = min(1.2, 1.0 + (positive_ratio - 0.7))  # Boost
        elif positive_ratio < 0.3:
            factor = max(0.7, 0.7 + positive_ratio)  # Penalize
        else:
            factor = 1.0

        adjustment = ConfidenceAdjustment(
            reason=AdjustmentReason.USER_FEEDBACK,
            factor=factor,
            description=f"Feedback: {positive_feedback_count}+ / {negative_feedback_count}-",
        )
        adjusted, _ = self.adjust(confidence, [adjustment])
        return adjusted


class ConfidenceAggregator:
    """Aggregate confidence scores from multiple sources."""

    def __init__(self, scorer: ConfidenceScorer | None = None):
        self.scorer = scorer or ConfidenceScorer()

    def mean(self, confidences: list[float]) -> float:
        """Calculate mean confidence."""
        if not confidences:
            return self.scorer.default_confidence
        return sum(confidences) / len(confidences)

    def weighted_mean(
        self,
        confidences: list[float],
        weights: list[float],
    ) -> float:
        """Calculate weighted mean confidence."""
        if not confidences or not weights:
            return self.scorer.default_confidence
        if len(confidences) != len(weights):
            raise ValueError("Confidences and weights must have same length")

        total_weight = sum(weights)
        if total_weight == 0:
            return self.mean(confidences)

        weighted_sum = sum(c * w for c, w in zip(confidences, weights))
        return weighted_sum / total_weight

    def min_confidence(self, confidences: list[float]) -> float:
        """Return minimum confidence (conservative approach)."""
        if not confidences:
            return self.scorer.default_confidence
        return min(confidences)

    def max_confidence(self, confidences: list[float]) -> float:
        """Return maximum confidence (optimistic approach)."""
        if not confidences:
            return self.scorer.default_confidence
        return max(confidences)

    def consensus(
        self,
        confidences: list[float],
        threshold: float = 0.7,
    ) -> float:
        """Calculate consensus confidence (agreement among sources)."""
        if not confidences:
            return self.scorer.default_confidence

        # Calculate variance
        mean = self.mean(confidences)
        variance = sum((c - mean) ** 2 for c in confidences) / len(confidences)

        # High variance = low consensus
        consensus_factor = max(0.5, 1.0 - variance)

        return mean * consensus_factor

    def bayesian_update(
        self,
        prior: float,
        likelihood: float,
        evidence_strength: float = 0.5,
    ) -> float:
        """Bayesian update of confidence given new evidence.

        Args:
            prior: Prior confidence (0-1)
            likelihood: Likelihood of observation given hypothesis (0-1)
            evidence_strength: How much weight to give new evidence (0-1)

        Returns:
            Posterior confidence
        """
        # Simplified Bayesian update
        # posterior ∝ prior * likelihood
        numerator = prior * likelihood
        denominator = (prior * likelihood) + ((1 - prior) * (1 - likelihood))

        if denominator == 0:
            return prior

        posterior = numerator / denominator

        # Blend with prior based on evidence strength
        return (evidence_strength * posterior) + ((1 - evidence_strength) * prior)


def calculate_risk_score(
    severity: Severity,
    likelihood: Likelihood,
    confidence: float = 1.0,
) -> float:
    """Calculate composite risk score (0-100).

    Uses a 5x5 risk matrix approach.

    Args:
        severity: Risk severity level
        likelihood: Risk likelihood level
        confidence: Confidence in the assessment

    Returns:
        Risk score from 0 to 100
    """
    severity_scores = {
        Severity.CRITICAL: 5,
        Severity.HIGH: 4,
        Severity.MEDIUM: 3,
        Severity.LOW: 2,
        Severity.INFORMATIONAL: 1,
    }

    likelihood_scores = {
        Likelihood.ALMOST_CERTAIN: 5,
        Likelihood.LIKELY: 4,
        Likelihood.POSSIBLE: 3,
        Likelihood.UNLIKELY: 2,
        Likelihood.RARE: 1,
    }

    sev_score = severity_scores.get(severity, 3)
    lik_score = likelihood_scores.get(likelihood, 3)

    # Base score: severity * likelihood, normalized to 0-100
    base_score = (sev_score * lik_score / 25) * 100

    # Apply confidence as a weight
    return base_score * confidence


def calibrate_confidence(
    raw_confidence: float,
    calibration_curve: Callable[[float], float] | None = None,
) -> float:
    """Apply calibration to raw LLM confidence scores.

    LLMs tend to be overconfident. This applies a calibration curve.

    Args:
        raw_confidence: Raw confidence from LLM
        calibration_curve: Optional custom calibration function

    Returns:
        Calibrated confidence
    """
    if calibration_curve:
        return calibration_curve(raw_confidence)

    # Default calibration: compress high confidences
    # LLMs often give 0.8-0.95 for moderate certainty
    if raw_confidence > 0.9:
        return 0.85 + (raw_confidence - 0.9) * 0.5  # 0.9->0.85, 1.0->0.9
    elif raw_confidence > 0.7:
        return 0.6 + (raw_confidence - 0.7) * 1.25  # 0.7->0.6, 0.9->0.85
    else:
        return raw_confidence * 0.85  # Scale down lower confidences slightly
```

### 3. Create `/services/insight-engine/src/aswa_insight/scoring/quality.py`
Document and extraction quality scoring:

```python
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
```

## Test Requirements

### Create `/services/insight-engine/tests/scoring/__init__.py`

### Create `/services/insight-engine/tests/scoring/test_confidence.py`
```python
import pytest
from aswa_insight.scoring.confidence import (
    ConfidenceScorer,
    ConfidenceAdjuster,
    ConfidenceAggregator,
    AdjustmentReason,
    ConfidenceAdjustment,
    calculate_risk_score,
    calibrate_confidence,
)
from aswa_insight.models.base import ConfidenceLevel
from aswa_insight.models.risks import Severity, Likelihood


class TestConfidenceScorer:
    def test_validate_normal_confidence(self):
        """Test validation of normal confidence value."""
        scorer = ConfidenceScorer()
        assert scorer.validate(0.75) == 0.75

    def test_validate_clamps_high(self):
        """Test clamping of too-high confidence."""
        scorer = ConfidenceScorer()
        assert scorer.validate(1.5) == 1.0

    def test_validate_clamps_low(self):
        """Test clamping of negative confidence."""
        scorer = ConfidenceScorer()
        assert scorer.validate(-0.5) == 0.0

    def test_validate_none_returns_default(self):
        """Test None returns default confidence."""
        scorer = ConfidenceScorer(default_confidence=0.6)
        assert scorer.validate(None) == 0.6

    def test_to_level_very_high(self):
        """Test conversion to VERY_HIGH level."""
        scorer = ConfidenceScorer()
        assert scorer.to_level(0.9) == ConfidenceLevel.VERY_HIGH

    def test_to_level_high(self):
        """Test conversion to HIGH level."""
        scorer = ConfidenceScorer()
        assert scorer.to_level(0.7) == ConfidenceLevel.HIGH

    def test_to_level_medium(self):
        """Test conversion to MEDIUM level."""
        scorer = ConfidenceScorer()
        assert scorer.to_level(0.5) == ConfidenceLevel.MEDIUM

    def test_to_level_low(self):
        """Test conversion to LOW level."""
        scorer = ConfidenceScorer()
        assert scorer.to_level(0.3) == ConfidenceLevel.LOW

    def test_to_level_very_low(self):
        """Test conversion to VERY_LOW level."""
        scorer = ConfidenceScorer()
        assert scorer.to_level(0.1) == ConfidenceLevel.VERY_LOW

    def test_from_level_roundtrip(self):
        """Test level to confidence conversion."""
        scorer = ConfidenceScorer()
        for level in ConfidenceLevel:
            confidence = scorer.from_level(level)
            assert 0.0 <= confidence <= 1.0


class TestConfidenceAdjuster:
    def test_adjust_single_factor(self):
        """Test single adjustment."""
        adjuster = ConfidenceAdjuster()
        adj = ConfidenceAdjustment(
            reason=AdjustmentReason.SOURCE_QUALITY,
            factor=0.9,
            description="Test"
        )
        result, applied = adjuster.adjust(0.8, [adj])
        assert result == pytest.approx(0.72)
        assert len(applied) == 1

    def test_adjust_multiple_factors(self):
        """Test multiple adjustments."""
        adjuster = ConfidenceAdjuster()
        adjustments = [
            ConfidenceAdjustment(AdjustmentReason.SOURCE_QUALITY, 0.9, "Test1"),
            ConfidenceAdjustment(AdjustmentReason.TEXT_LENGTH, 0.95, "Test2"),
        ]
        result, applied = adjuster.adjust(0.8, adjustments)
        assert result == pytest.approx(0.8 * 0.9 * 0.95)
        assert len(applied) == 2

    def test_adjust_clamps_result(self):
        """Test result is clamped to valid range."""
        adjuster = ConfidenceAdjuster()
        adj = ConfidenceAdjustment(AdjustmentReason.USER_FEEDBACK, 1.5, "Boost")
        result, _ = adjuster.adjust(0.9, [adj])
        assert result <= 1.0

    def test_adjust_for_source_quality_high(self):
        """Test source quality adjustment for high reliability."""
        adjuster = ConfidenceAdjuster()
        result = adjuster.adjust_for_source_quality(0.8, 1.0)
        assert result == 0.8  # No penalty for perfect source

    def test_adjust_for_source_quality_low(self):
        """Test source quality adjustment for low reliability."""
        adjuster = ConfidenceAdjuster()
        result = adjuster.adjust_for_source_quality(0.8, 0.0)
        assert result < 0.8  # Penalized

    def test_adjust_for_text_length_short(self):
        """Test penalty for very short text."""
        adjuster = ConfidenceAdjuster()
        result = adjuster.adjust_for_text_length(0.8, 50)
        assert result < 0.8

    def test_adjust_for_text_length_optimal(self):
        """Test no penalty for optimal length."""
        adjuster = ConfidenceAdjuster()
        result = adjuster.adjust_for_text_length(0.8, 500)
        assert result == 0.8

    def test_adjust_for_user_feedback_positive(self):
        """Test boost from positive feedback."""
        adjuster = ConfidenceAdjuster()
        result = adjuster.adjust_for_user_feedback(0.7, positive_feedback_count=8, negative_feedback_count=2)
        assert result > 0.7

    def test_adjust_for_user_feedback_negative(self):
        """Test penalty from negative feedback."""
        adjuster = ConfidenceAdjuster()
        result = adjuster.adjust_for_user_feedback(0.7, positive_feedback_count=2, negative_feedback_count=8)
        assert result < 0.7


class TestConfidenceAggregator:
    def test_mean_normal(self):
        """Test mean of normal values."""
        agg = ConfidenceAggregator()
        assert agg.mean([0.6, 0.8, 0.7]) == pytest.approx(0.7)

    def test_mean_empty(self):
        """Test mean of empty list."""
        agg = ConfidenceAggregator()
        assert agg.mean([]) == 0.5  # Default

    def test_weighted_mean(self):
        """Test weighted mean calculation."""
        agg = ConfidenceAggregator()
        result = agg.weighted_mean([0.6, 0.8], [1.0, 3.0])
        assert result == pytest.approx(0.75)  # (0.6*1 + 0.8*3) / 4

    def test_min_confidence(self):
        """Test minimum confidence."""
        agg = ConfidenceAggregator()
        assert agg.min_confidence([0.6, 0.8, 0.7]) == 0.6

    def test_max_confidence(self):
        """Test maximum confidence."""
        agg = ConfidenceAggregator()
        assert agg.max_confidence([0.6, 0.8, 0.7]) == 0.8

    def test_consensus_high_agreement(self):
        """Test consensus with high agreement."""
        agg = ConfidenceAggregator()
        result = agg.consensus([0.75, 0.76, 0.74])
        assert result > 0.7  # High consensus

    def test_consensus_low_agreement(self):
        """Test consensus with low agreement."""
        agg = ConfidenceAggregator()
        result = agg.consensus([0.3, 0.9, 0.5])
        assert result < 0.6  # Low consensus penalized

    def test_bayesian_update_strong_evidence(self):
        """Test Bayesian update with strong supporting evidence."""
        agg = ConfidenceAggregator()
        result = agg.bayesian_update(prior=0.5, likelihood=0.9, evidence_strength=0.8)
        assert result > 0.5  # Increased

    def test_bayesian_update_contradicting_evidence(self):
        """Test Bayesian update with contradicting evidence."""
        agg = ConfidenceAggregator()
        result = agg.bayesian_update(prior=0.7, likelihood=0.2, evidence_strength=0.8)
        assert result < 0.7  # Decreased


class TestRiskScore:
    def test_critical_almost_certain(self):
        """Test highest risk score."""
        score = calculate_risk_score(Severity.CRITICAL, Likelihood.ALMOST_CERTAIN)
        assert score == 100.0

    def test_informational_rare(self):
        """Test lowest risk score."""
        score = calculate_risk_score(Severity.INFORMATIONAL, Likelihood.RARE)
        assert score == 4.0  # 1*1/25*100

    def test_medium_possible(self):
        """Test middle risk score."""
        score = calculate_risk_score(Severity.MEDIUM, Likelihood.POSSIBLE)
        assert score == 36.0  # 3*3/25*100

    def test_confidence_scales_score(self):
        """Test confidence affects final score."""
        full_score = calculate_risk_score(Severity.HIGH, Likelihood.LIKELY, confidence=1.0)
        half_score = calculate_risk_score(Severity.HIGH, Likelihood.LIKELY, confidence=0.5)
        assert half_score == full_score * 0.5


class TestCalibrateConfidence:
    def test_high_confidence_compressed(self):
        """Test high confidence is compressed."""
        calibrated = calibrate_confidence(0.95)
        assert calibrated < 0.95

    def test_low_confidence_preserved(self):
        """Test low confidence roughly preserved."""
        calibrated = calibrate_confidence(0.3)
        assert 0.2 < calibrated < 0.4

    def test_custom_calibration(self):
        """Test custom calibration function."""
        custom = lambda x: x * 0.5
        calibrated = calibrate_confidence(0.8, calibration_curve=custom)
        assert calibrated == 0.4
```

### Create `/services/insight-engine/tests/scoring/test_quality.py`
```python
import pytest
from aswa_insight.scoring.quality import (
    QualityScorer,
    DocumentQuality,
    ExtractionQuality,
    QualityLevel,
)
from aswa_insight.models.base import ExtractedInsightBase, SourceReference


class TestDocumentQuality:
    def test_quality_score_calculation(self):
        """Test quality score calculation."""
        dq = DocumentQuality(
            document_id="test",
            text_length=1000,
            word_count=200,
            sentence_count=20,
            has_structure=True,
            readability_score=65.0,
            noise_ratio=0.1,
        )
        assert 0.0 <= dq.quality_score <= 1.0

    def test_quality_level_excellent(self):
        """Test excellent quality level."""
        dq = DocumentQuality(
            document_id="test",
            text_length=5000,
            word_count=1000,
            sentence_count=50,
            has_structure=True,
            readability_score=60.0,
            noise_ratio=0.05,
        )
        assert dq.quality_level in [QualityLevel.EXCELLENT, QualityLevel.GOOD]

    def test_quality_level_poor(self):
        """Test poor quality level."""
        dq = DocumentQuality(
            document_id="test",
            text_length=50,
            word_count=10,
            sentence_count=1,
            has_structure=False,
            readability_score=20.0,
            noise_ratio=0.5,
        )
        assert dq.quality_level in [QualityLevel.POOR, QualityLevel.UNUSABLE]


class TestExtractionQuality:
    def test_quality_score_with_insights(self):
        """Test quality score with insights."""
        eq = ExtractionQuality(
            document_id="test",
            extraction_type="entity",
            insight_count=10,
            avg_confidence=0.8,
            min_confidence=0.6,
            max_confidence=0.95,
            high_confidence_count=5,
            low_confidence_count=1,
            has_sources=True,
            processing_time_ms=500,
        )
        assert 0.0 <= eq.quality_score <= 1.0
        assert eq.quality_level != QualityLevel.UNUSABLE

    def test_quality_score_empty_extraction(self):
        """Test quality score for empty extraction."""
        eq = ExtractionQuality(
            document_id="test",
            extraction_type="entity",
            insight_count=0,
            avg_confidence=0.0,
            min_confidence=0.0,
            max_confidence=0.0,
            high_confidence_count=0,
            low_confidence_count=0,
            has_sources=False,
            processing_time_ms=100,
        )
        assert eq.quality_score == 0.3


class TestQualityScorer:
    def test_assess_document(self):
        """Test document assessment."""
        scorer = QualityScorer()
        text = "This is a test document. " * 50
        result = scorer.assess_document("doc-1", text)
        assert isinstance(result, DocumentQuality)
        assert result.word_count > 0

    def test_assess_extraction_empty(self):
        """Test extraction assessment with no insights."""
        scorer = QualityScorer()
        result = scorer.assess_extraction(
            "doc-1", "entity", [], 100
        )
        assert result.insight_count == 0

    def test_calculate_overall_quality(self):
        """Test overall quality calculation."""
        scorer = QualityScorer()

        doc_quality = DocumentQuality(
            document_id="test",
            text_length=1000,
            word_count=200,
            sentence_count=20,
            has_structure=True,
            readability_score=60.0,
            noise_ratio=0.1,
        )

        ext_quality = ExtractionQuality(
            document_id="test",
            extraction_type="entity",
            insight_count=5,
            avg_confidence=0.8,
            min_confidence=0.6,
            max_confidence=0.9,
            high_confidence_count=3,
            low_confidence_count=0,
            has_sources=True,
            processing_time_ms=200,
        )

        overall = scorer.calculate_overall_quality(doc_quality, [ext_quality])
        assert 0.0 <= overall <= 1.0
```

## Verification

1. Run tests: `cd /services/insight-engine && python -m pytest tests/scoring/ -v`
2. Verify imports: `python -c "from aswa_insight.scoring import *"`
3. Test risk score calculation with various inputs
4. Verify calibration reduces overconfident LLM scores
