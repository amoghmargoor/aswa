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
            noise_ratio=0.8,  # Very high noise ratio to push into poor range
        )
        assert dq.quality_level in [QualityLevel.POOR, QualityLevel.UNUSABLE, QualityLevel.FAIR]


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
