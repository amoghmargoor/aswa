from dataclasses import dataclass
from enum import Enum
from typing import Callable
import structlog

from aswa_insight.models.base import ConfidenceLevel
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
