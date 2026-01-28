import pytest
from aswa_query.parser.entities import EntityExtractor
from aswa_query.parser.models import EntityType


class TestEntityExtractor:
    @pytest.fixture
    def extractor(self):
        return EntityExtractor()

    def test_extract_money(self, extractor):
        """Test money entity extraction."""
        entities = extractor.extract("The revenue was $5 million")
        money_entities = [e for e in entities if e.entity_type == EntityType.MONEY]
        assert len(money_entities) >= 1

    def test_extract_percentage(self, extractor):
        """Test percentage extraction."""
        entities = extractor.extract("Growth was 15% year over year")
        pct_entities = [e for e in entities if e.entity_type == EntityType.PERCENTAGE]
        assert len(pct_entities) == 1
        assert "15%" in pct_entities[0].text

    def test_extract_date(self, extractor):
        """Test date extraction."""
        entities = extractor.extract("The meeting is on January 15, 2024")
        date_entities = [e for e in entities if e.entity_type == EntityType.DATE]
        assert len(date_entities) >= 1

    def test_extract_organization(self, extractor):
        """Test organization extraction."""
        entities = extractor.extract("Acme Corporation reported earnings")
        org_entities = [e for e in entities if e.entity_type == EntityType.ORGANIZATION]
        assert len(org_entities) >= 1

    def test_no_overlapping_entities(self, extractor):
        """Test overlapping entities are handled."""
        entities = extractor.extract("Acme Corp reported $50 million in Q1 2024")
        # Check no overlapping positions
        positions = [(e.start_pos, e.end_pos) for e in entities]
        for i, (start1, end1) in enumerate(positions):
            for j, (start2, end2) in enumerate(positions):
                if i != j:
                    assert not (start1 < end2 and end1 > start2)
