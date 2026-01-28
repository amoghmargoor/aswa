"""Tests for pattern extraction models."""

import pytest
from datetime import datetime
from uuid import uuid4

from aswa_insight.models import (
    ExtractedPattern,
    PatternType,
    TrendDirection,
    PatternFrequency,
    DataPoint,
    PatternExtractionResult,
)


class TestExtractedPattern:
    """Tests for ExtractedPattern model."""

    def test_valid_pattern_creation(self):
        """Test creating valid pattern."""
        pattern = ExtractedPattern(
            title="Revenue Growth Trend",
            description="Steady revenue growth over the past year",
            pattern_type=PatternType.TREND,
            confidence=0.9,
        )

        assert pattern.title == "Revenue Growth Trend"
        assert pattern.pattern_type == PatternType.TREND
        assert pattern.confidence == 0.9
        assert pattern.frequency is None
        assert pattern.trend_direction is None
        assert pattern.data_points == []
        assert pattern.implications == []

    def test_pattern_with_data_points(self):
        """Test pattern with data points."""
        dp1 = DataPoint(
            label="Q1",
            value=100000.0,
            timestamp=datetime(2024, 3, 31),
        )

        dp2 = DataPoint(
            label="Q2",
            value=120000.0,
            timestamp=datetime(2024, 6, 30),
        )

        dp3 = DataPoint(
            label="Q3",
            value=150000.0,
            timestamp=datetime(2024, 9, 30),
        )

        pattern = ExtractedPattern(
            title="Quarterly Revenue Growth",
            description="Revenue increasing each quarter",
            pattern_type=PatternType.TREND,
            trend_direction=TrendDirection.INCREASING,
            frequency=PatternFrequency.QUARTERLY,
            confidence=0.95,
            data_points=[dp1, dp2, dp3],
        )

        assert len(pattern.data_points) == 3
        assert pattern.data_points[0].value == 100000.0
        assert pattern.data_points[2].label == "Q3"
        assert pattern.trend_direction == TrendDirection.INCREASING

    def test_all_pattern_types(self):
        """Test all pattern type enum values."""
        pattern_types = [
            PatternType.TREND,
            PatternType.CORRELATION,
            PatternType.ANOMALY,
            PatternType.CYCLE,
            PatternType.THRESHOLD,
            PatternType.COMPARISON,
            PatternType.DISTRIBUTION,
            PatternType.SEQUENCE,
            PatternType.OTHER,
        ]

        for ptype in pattern_types:
            pattern = ExtractedPattern(
                title="Test Pattern",
                description="Test description",
                pattern_type=ptype,
                confidence=0.8,
            )
            assert pattern.pattern_type == ptype

    def test_trend_direction(self):
        """Test trend direction values."""
        directions = [
            TrendDirection.INCREASING,
            TrendDirection.DECREASING,
            TrendDirection.STABLE,
            TrendDirection.VOLATILE,
            TrendDirection.CYCLICAL,
        ]

        for direction in directions:
            pattern = ExtractedPattern(
                title="Test Trend",
                description="Test trend pattern",
                pattern_type=PatternType.TREND,
                trend_direction=direction,
                confidence=0.8,
            )
            assert pattern.trend_direction == direction

    def test_pattern_frequency(self):
        """Test pattern frequency values."""
        frequencies = [
            PatternFrequency.DAILY,
            PatternFrequency.WEEKLY,
            PatternFrequency.MONTHLY,
            PatternFrequency.QUARTERLY,
            PatternFrequency.YEARLY,
            PatternFrequency.IRREGULAR,
            PatternFrequency.ONE_TIME,
        ]

        for freq in frequencies:
            pattern = ExtractedPattern(
                title="Test Pattern",
                description="Test recurring pattern",
                pattern_type=PatternType.CYCLE,
                frequency=freq,
                confidence=0.8,
            )
            assert pattern.frequency == freq

    def test_pattern_with_implications(self):
        """Test pattern with implications."""
        pattern = ExtractedPattern(
            title="Customer Churn Pattern",
            description="Increased churn after 6 months",
            pattern_type=PatternType.CORRELATION,
            confidence=0.85,
            implications=[
                "Need better onboarding",
                "Improve 6-month engagement",
                "Review pricing strategy",
            ],
        )

        assert len(pattern.implications) == 3
        assert "Need better onboarding" in pattern.implications

    def test_pattern_with_related_entities(self):
        """Test pattern with related entities."""
        pattern = ExtractedPattern(
            title="Sales Performance Pattern",
            description="Sales spike during marketing campaigns",
            pattern_type=PatternType.CORRELATION,
            confidence=0.9,
            related_entities=["Marketing Department", "Sales Team", "Q4 Campaign"],
        )

        assert len(pattern.related_entities) == 3
        assert "Marketing Department" in pattern.related_entities

    def test_data_point_with_string_value(self):
        """Test data point with string value."""
        dp = DataPoint(
            label="Category A",
            value="High performance",
        )

        assert dp.label == "Category A"
        assert dp.value == "High performance"
        assert dp.timestamp is None

    def test_data_point_with_numeric_value(self):
        """Test data point with numeric value."""
        dp = DataPoint(
            label="Metric",
            value=42.5,
            timestamp=datetime(2024, 1, 1),
        )

        assert dp.value == 42.5
        assert dp.timestamp is not None


class TestPatternExtractionResult:
    """Tests for PatternExtractionResult model."""

    def test_empty_result(self):
        """Test empty pattern extraction result."""
        result = PatternExtractionResult()

        assert result.patterns == []
        assert result.document_id is None
        assert result.extraction_timestamp is not None

    def test_result_with_patterns(self):
        """Test result with multiple patterns."""
        pattern1 = ExtractedPattern(
            title="Pattern 1",
            description="First pattern",
            pattern_type=PatternType.TREND,
            confidence=0.9,
        )

        pattern2 = ExtractedPattern(
            title="Pattern 2",
            description="Second pattern",
            pattern_type=PatternType.ANOMALY,
            confidence=0.85,
        )

        doc_id = uuid4()
        result = PatternExtractionResult(
            patterns=[pattern1, pattern2], document_id=doc_id
        )

        assert len(result.patterns) == 2
        assert result.document_id == doc_id
        assert result.patterns[0].title == "Pattern 1"
        assert result.patterns[1].pattern_type == PatternType.ANOMALY
