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
