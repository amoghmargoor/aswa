"""Tests for risk extraction models."""

import pytest
from uuid import uuid4

from aswa_insight.models import (
    ExtractedRisk,
    RiskCategory,
    Severity,
    Likelihood,
    TimeHorizon,
    MitigationStrategy,
    RiskExtractionResult,
)


class TestExtractedRisk:
    """Tests for ExtractedRisk model."""

    def test_valid_risk_creation(self):
        """Test creating valid risk."""
        risk = ExtractedRisk(
            title="Data Breach Risk",
            description="Potential unauthorized access to customer data",
            category=RiskCategory.SECURITY,
            severity=Severity.HIGH,
            likelihood=Likelihood.POSSIBLE,
            impact_description="Could result in customer data exposure",
            confidence=0.85,
        )

        assert risk.title == "Data Breach Risk"
        assert risk.category == RiskCategory.SECURITY
        assert risk.severity == Severity.HIGH
        assert risk.likelihood == Likelihood.POSSIBLE
        assert risk.confidence == 0.85
        assert risk.affected_areas == []
        assert risk.related_entities == []
        assert risk.mitigations == []

    def test_risk_score_calculation(self):
        """Test risk score from severity/likelihood."""
        risk = ExtractedRisk(
            title="Test Risk",
            description="Test description",
            category=RiskCategory.OPERATIONAL,
            severity=Severity.CRITICAL,
            likelihood=Likelihood.LIKELY,
            impact_description="High impact",
            confidence=0.9,
            risk_score=85.0,
        )

        assert risk.risk_score == 85.0

        # Test valid bounds
        risk_low = ExtractedRisk(
            title="Test Risk",
            description="Test description",
            category=RiskCategory.OPERATIONAL,
            severity=Severity.LOW,
            likelihood=Likelihood.RARE,
            impact_description="Low impact",
            confidence=0.9,
            risk_score=0.0,
        )
        assert risk_low.risk_score == 0.0

        risk_high = ExtractedRisk(
            title="Test Risk",
            description="Test description",
            category=RiskCategory.OPERATIONAL,
            severity=Severity.CRITICAL,
            likelihood=Likelihood.ALMOST_CERTAIN,
            impact_description="Critical impact",
            confidence=0.9,
            risk_score=100.0,
        )
        assert risk_high.risk_score == 100.0

        # Test invalid bounds
        with pytest.raises(Exception):
            ExtractedRisk(
                title="Test Risk",
                description="Test description",
                category=RiskCategory.OPERATIONAL,
                severity=Severity.CRITICAL,
                likelihood=Likelihood.LIKELY,
                impact_description="High impact",
                confidence=0.9,
                risk_score=150.0,
            )

    def test_risk_with_mitigations(self):
        """Test risk with mitigation strategies."""
        mitigation1 = MitigationStrategy(
            title="Implement MFA",
            description="Multi-factor authentication for all users",
            effort="medium",
            effectiveness="high",
        )

        mitigation2 = MitigationStrategy(
            title="Security Training",
            description="Mandatory security awareness training",
            effort="low",
            effectiveness="medium",
        )

        risk = ExtractedRisk(
            title="Account Takeover Risk",
            description="Risk of unauthorized account access",
            category=RiskCategory.SECURITY,
            severity=Severity.HIGH,
            likelihood=Likelihood.LIKELY,
            impact_description="Unauthorized access to user accounts",
            confidence=0.9,
            mitigations=[mitigation1, mitigation2],
        )

        assert len(risk.mitigations) == 2
        assert risk.mitigations[0].title == "Implement MFA"
        assert risk.mitigations[1].effort == "low"

    def test_all_severity_levels(self):
        """Test all severity enum values."""
        severities = [
            Severity.CRITICAL,
            Severity.HIGH,
            Severity.MEDIUM,
            Severity.LOW,
            Severity.INFORMATIONAL,
        ]

        for severity in severities:
            risk = ExtractedRisk(
                title="Test Risk",
                description="Test description",
                category=RiskCategory.OPERATIONAL,
                severity=severity,
                likelihood=Likelihood.POSSIBLE,
                impact_description="Test impact",
                confidence=0.8,
            )
            assert risk.severity == severity

    def test_all_likelihood_levels(self):
        """Test all likelihood enum values."""
        likelihoods = [
            Likelihood.ALMOST_CERTAIN,
            Likelihood.LIKELY,
            Likelihood.POSSIBLE,
            Likelihood.UNLIKELY,
            Likelihood.RARE,
        ]

        for likelihood in likelihoods:
            risk = ExtractedRisk(
                title="Test Risk",
                description="Test description",
                category=RiskCategory.OPERATIONAL,
                severity=Severity.MEDIUM,
                likelihood=likelihood,
                impact_description="Test impact",
                confidence=0.8,
            )
            assert risk.likelihood == likelihood

    def test_risk_with_time_horizon(self):
        """Test risk with time horizon."""
        risk = ExtractedRisk(
            title="Market Risk",
            description="Potential market downturn",
            category=RiskCategory.MARKET,
            severity=Severity.MEDIUM,
            likelihood=Likelihood.POSSIBLE,
            impact_description="Revenue decline",
            confidence=0.7,
            time_horizon=TimeHorizon.SHORT_TERM,
        )

        assert risk.time_horizon == TimeHorizon.SHORT_TERM


class TestMitigationStrategy:
    """Tests for MitigationStrategy model."""

    def test_valid_mitigation(self):
        """Test creating valid mitigation."""
        mitigation = MitigationStrategy(
            title="Enable Encryption",
            description="Encrypt all data at rest and in transit",
            effort="high",
            effectiveness="high",
        )

        assert mitigation.title == "Enable Encryption"
        assert mitigation.effort == "high"
        assert mitigation.effectiveness == "high"

    def test_mitigation_effort_levels(self):
        """Test all effort level values."""
        for effort in ["low", "medium", "high"]:
            mitigation = MitigationStrategy(
                title="Test Mitigation",
                description="Test description",
                effort=effort,
                effectiveness="medium",
            )
            assert mitigation.effort == effort

    def test_mitigation_effectiveness_levels(self):
        """Test all effectiveness level values."""
        for effectiveness in ["low", "medium", "high"]:
            mitigation = MitigationStrategy(
                title="Test Mitigation",
                description="Test description",
                effort="medium",
                effectiveness=effectiveness,
            )
            assert mitigation.effectiveness == effectiveness


class TestRiskExtractionResult:
    """Tests for RiskExtractionResult model."""

    def test_empty_result(self):
        """Test empty risk extraction result."""
        result = RiskExtractionResult()

        assert result.risks == []
        assert result.overall_risk_level is None
        assert result.document_id is None
        assert result.extraction_timestamp is not None

    def test_result_with_risks(self):
        """Test result with multiple risks."""
        risk1 = ExtractedRisk(
            title="Risk 1",
            description="First risk",
            category=RiskCategory.SECURITY,
            severity=Severity.HIGH,
            likelihood=Likelihood.LIKELY,
            impact_description="High impact",
            confidence=0.9,
        )

        risk2 = ExtractedRisk(
            title="Risk 2",
            description="Second risk",
            category=RiskCategory.OPERATIONAL,
            severity=Severity.MEDIUM,
            likelihood=Likelihood.POSSIBLE,
            impact_description="Medium impact",
            confidence=0.8,
        )

        doc_id = uuid4()
        result = RiskExtractionResult(
            risks=[risk1, risk2],
            overall_risk_level=Severity.HIGH,
            document_id=doc_id,
        )

        assert len(result.risks) == 2
        assert result.overall_risk_level == Severity.HIGH
        assert result.document_id == doc_id
