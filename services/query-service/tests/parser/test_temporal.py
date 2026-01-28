import pytest
from datetime import datetime, timedelta
from aswa_query.parser.temporal import TemporalParser


class TestTemporalParser:
    @pytest.fixture
    def parser(self):
        return TemporalParser()

    def test_last_n_days(self, parser):
        """Test 'last N days' parsing."""
        result = parser.parse("Show data from last 30 days")
        assert result is not None
        assert result.start is not None
        assert result.end is not None
        assert (result.end - result.start).days >= 29

    def test_this_month(self, parser):
        """Test 'this month' parsing."""
        result = parser.parse("What happened this month?")
        assert result is not None
        assert result.start.day == 1
        assert result.start.month == datetime.utcnow().month

    def test_last_quarter(self, parser):
        """Test 'last quarter' parsing."""
        result = parser.parse("Report for last quarter")
        assert result is not None
        assert result.relative == "last quarter"

    def test_explicit_quarter(self, parser):
        """Test explicit quarter parsing."""
        result = parser.parse("Show me Q1 2024 data")
        assert result is not None
        assert result.explicit is True
        assert result.start.year == 2024
        assert result.start.month == 1

    def test_ytd(self, parser):
        """Test year to date parsing."""
        result = parser.parse("Show YTD performance")
        assert result is not None
        assert result.start.month == 1
        assert result.start.day == 1

    def test_no_temporal(self, parser):
        """Test query with no temporal expression."""
        result = parser.parse("What are the main risks?")
        assert result is None
