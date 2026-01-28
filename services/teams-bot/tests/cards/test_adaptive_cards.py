import pytest
from aswa_teams.cards.adaptive_cards import (
    create_answer_card,
    create_insights_card,
    create_error_card,
    create_welcome_card,
    create_help_card,
    create_digest_card,
    create_feedback_card,
    create_query_form_card,
)


class TestAnswerCard:
    def test_create_answer_card(self):
        """Test answer card creation."""
        card = create_answer_card(
            query="What are the risks?",
            answer="The main risks are...",
            citations=[
                {"document_name": "Report.pdf", "page_number": 5},
            ],
            confidence=0.85,
            query_id="test-123",
        )

        assert card is not None
        assert card.content_type == "application/vnd.microsoft.card.adaptive"

    def test_create_answer_card_no_citations(self):
        """Test answer card without citations."""
        card = create_answer_card(
            query="Test query",
            answer="Test answer",
            citations=[],
            confidence=0.7,
            query_id="test-456",
        )

        assert card is not None

    def test_create_answer_card_low_confidence(self):
        """Test answer card with low confidence."""
        card = create_answer_card(
            query="Test query",
            answer="Test answer",
            citations=[],
            confidence=0.3,
            query_id="test-789",
        )

        assert card is not None


class TestInsightsCard:
    def test_create_insights_card(self):
        """Test insights card creation."""
        card = create_insights_card(
            insights=[
                {
                    "title": "Risk 1",
                    "description": "Description of risk",
                    "type": "risk",
                    "confidence": 0.9,
                },
            ],
            insight_type="risks",
        )

        assert card is not None

    def test_create_insights_card_empty(self):
        """Test insights card with no insights."""
        card = create_insights_card([], "all")
        assert card is not None

    def test_create_insights_card_multiple(self):
        """Test insights card with multiple insights."""
        card = create_insights_card(
            insights=[
                {"title": "Risk 1", "description": "Desc 1", "type": "risk", "confidence": 0.9},
                {"title": "Opportunity 1", "description": "Desc 2", "type": "opportunity", "confidence": 0.8},
                {"title": "Trend 1", "description": "Desc 3", "type": "trend", "confidence": 0.7},
            ],
            insight_type="all",
        )
        assert card is not None


class TestErrorCard:
    def test_create_error_card(self):
        """Test error card creation."""
        card = create_error_card("Error Title", "Error message")
        assert card is not None


class TestWelcomeCard:
    def test_create_welcome_card(self):
        """Test welcome card creation."""
        card = create_welcome_card("ASWA Bot")
        assert card is not None

    def test_create_welcome_card_default_name(self):
        """Test welcome card with default name."""
        card = create_welcome_card()
        assert card is not None


class TestHelpCard:
    def test_create_help_card(self):
        """Test help card creation."""
        card = create_help_card()
        assert card is not None


class TestDigestCard:
    def test_create_digest_card(self):
        """Test digest card creation."""
        card = create_digest_card(
            digest={
                "summary": "This week's summary",
                "sections": [
                    {
                        "name": "New Risks",
                        "items": [{"title": "Risk 1"}],
                    },
                ],
            },
            period="weekly",
        )

        assert card is not None

    def test_create_digest_card_empty(self):
        """Test digest card with empty digest."""
        card = create_digest_card(digest={}, period="daily")
        assert card is not None


class TestFeedbackCard:
    def test_create_feedback_card(self):
        """Test feedback card creation."""
        card = create_feedback_card("query-123")
        assert card is not None


class TestQueryFormCard:
    def test_create_query_form_card(self):
        """Test query form card creation."""
        card = create_query_form_card()
        assert card is not None
