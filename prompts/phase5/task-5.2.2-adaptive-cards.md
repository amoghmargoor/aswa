# Task 5.2.2: Microsoft Teams - Adaptive Cards

## Context

You are working on the ASWA Teams bot at `/services/teams-bot/`. The bot setup is complete (Task 5.2.1). Now we need to implement Adaptive Cards for rich content display.

## Objective

Create Adaptive Card templates that:
1. Display query answers with citations
2. Show insights with rich formatting
3. Provide interactive feedback options
4. Support forms for complex inputs
5. Display digest summaries

## Requirements

### 1. Create `/services/teams-bot/src/aswa_teams/cards/__init__.py`
```python
from .adaptive_cards import (
    create_answer_card,
    create_insights_card,
    create_error_card,
    create_welcome_card,
    create_help_card,
    create_digest_card,
    create_feedback_card,
    create_query_form_card,
)

__all__ = [
    "create_answer_card",
    "create_insights_card",
    "create_error_card",
    "create_welcome_card",
    "create_help_card",
    "create_digest_card",
    "create_feedback_card",
    "create_query_form_card",
]
```

### 2. Create `/services/teams-bot/src/aswa_teams/cards/adaptive_cards.py`
```python
from typing import Any
from botbuilder.schema import Attachment, CardAction, ActionTypes
from botbuilder.core import CardFactory


def create_answer_card(
    query: str,
    answer: str,
    citations: list[dict],
    confidence: float,
    query_id: str,
) -> Attachment:
    """Create an answer card with citations.

    Args:
        query: Original query
        answer: Generated answer
        citations: List of citations
        confidence: Confidence score
        query_id: Query identifier

    Returns:
        Adaptive card attachment
    """
    # Format citations
    citation_items = []
    for i, citation in enumerate(citations, 1):
        doc_name = citation.get("document_name", "Unknown")
        page = citation.get("page_number")

        citation_text = f"[{i}] {doc_name}"
        if page:
            citation_text += f", p.{page}"

        citation_items.append({
            "type": "TextBlock",
            "text": citation_text,
            "size": "Small",
            "color": "Accent",
            "wrap": True,
        })

    # Confidence indicator
    confidence_color = "Good" if confidence >= 0.7 else "Warning" if confidence >= 0.5 else "Attention"

    card = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
            {
                "type": "Container",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": "📝 Your Question",
                        "weight": "Bolder",
                        "size": "Small",
                        "color": "Accent",
                    },
                    {
                        "type": "TextBlock",
                        "text": query,
                        "wrap": True,
                        "isSubtle": True,
                    },
                ],
            },
            {
                "type": "Container",
                "separator": True,
                "spacing": "Medium",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": "💡 Answer",
                        "weight": "Bolder",
                        "size": "Small",
                        "color": "Good",
                    },
                    {
                        "type": "TextBlock",
                        "text": answer,
                        "wrap": True,
                    },
                ],
            },
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "👍 Helpful",
                "data": {
                    "action": {"type": "feedback", "data": {"query_id": query_id, "feedback": "helpful"}},
                },
            },
            {
                "type": "Action.Submit",
                "title": "👎 Not Helpful",
                "data": {
                    "action": {"type": "feedback", "data": {"query_id": query_id, "feedback": "not_helpful"}},
                },
            },
            {
                "type": "Action.ShowCard",
                "title": "🔄 Refine",
                "card": {
                    "type": "AdaptiveCard",
                    "body": [
                        {
                            "type": "Input.Text",
                            "id": "refined_query",
                            "placeholder": "Refine your question...",
                            "isMultiline": True,
                            "value": query,
                        },
                    ],
                    "actions": [
                        {
                            "type": "Action.Submit",
                            "title": "Ask",
                            "data": {
                                "action": {"type": "refine", "data": {}},
                            },
                        },
                    ],
                },
            },
        ],
    }

    # Add citations section if present
    if citation_items:
        card["body"].append({
            "type": "Container",
            "separator": True,
            "spacing": "Medium",
            "items": [
                {
                    "type": "TextBlock",
                    "text": "📚 Sources",
                    "weight": "Bolder",
                    "size": "Small",
                },
                *citation_items,
            ],
        })

    # Add confidence indicator
    card["body"].append({
        "type": "ColumnSet",
        "separator": True,
        "spacing": "Small",
        "columns": [
            {
                "type": "Column",
                "width": "auto",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": f"Confidence: {confidence:.0%}",
                        "size": "Small",
                        "color": confidence_color,
                    },
                ],
            },
            {
                "type": "Column",
                "width": "stretch",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": f"ID: {query_id[:8]}",
                        "size": "Small",
                        "isSubtle": True,
                        "horizontalAlignment": "Right",
                    },
                ],
            },
        ],
    })

    return CardFactory.adaptive_card(card)


def create_insights_card(
    insights: list[dict],
    insight_type: str = "all",
) -> Attachment:
    """Create a card displaying insights.

    Args:
        insights: List of insights
        insight_type: Type filter label

    Returns:
        Adaptive card attachment
    """
    insight_items = []

    for insight in insights[:5]:
        title = insight.get("title", "Untitled")
        description = insight.get("description", "")[:150]
        confidence = insight.get("confidence", 0)
        itype = insight.get("type", "unknown")

        emoji = "⚠️" if itype == "risk" else "💡" if itype == "opportunity" else "📌"
        color = "Attention" if itype == "risk" else "Good" if itype == "opportunity" else "Default"

        insight_items.append({
            "type": "Container",
            "separator": True,
            "spacing": "Medium",
            "items": [
                {
                    "type": "ColumnSet",
                    "columns": [
                        {
                            "type": "Column",
                            "width": "stretch",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": f"{emoji} {title}",
                                    "weight": "Bolder",
                                    "wrap": True,
                                    "color": color,
                                },
                            ],
                        },
                        {
                            "type": "Column",
                            "width": "auto",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": f"{confidence:.0%}",
                                    "size": "Small",
                                    "isSubtle": True,
                                },
                            ],
                        },
                    ],
                },
                {
                    "type": "TextBlock",
                    "text": description + "..." if len(description) >= 150 else description,
                    "wrap": True,
                    "size": "Small",
                },
            ],
        })

    card = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "text": f"📊 {insight_type.title()} Insights",
                "weight": "Bolder",
                "size": "Large",
            },
            *insight_items,
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "View Risks",
                "data": {"action": {"type": "insights", "data": {"type": "risks"}}},
            },
            {
                "type": "Action.Submit",
                "title": "View Opportunities",
                "data": {"action": {"type": "insights", "data": {"type": "opportunities"}}},
            },
        ],
    }

    if not insight_items:
        card["body"].append({
            "type": "TextBlock",
            "text": "No insights found.",
            "isSubtle": True,
        })

    return CardFactory.adaptive_card(card)


def create_error_card(
    title: str,
    message: str,
) -> Attachment:
    """Create an error card.

    Args:
        title: Error title
        message: Error message

    Returns:
        Adaptive card attachment
    """
    card = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
            {
                "type": "Container",
                "style": "attention",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": f"❌ {title}",
                        "weight": "Bolder",
                        "color": "Attention",
                    },
                    {
                        "type": "TextBlock",
                        "text": message,
                        "wrap": True,
                    },
                ],
            },
        ],
    }

    return CardFactory.adaptive_card(card)


def create_welcome_card(bot_name: str = "ASWA") -> Attachment:
    """Create a welcome card.

    Args:
        bot_name: Bot display name

    Returns:
        Adaptive card attachment
    """
    card = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
            {
                "type": "Container",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": f"👋 Welcome to {bot_name}!",
                        "weight": "Bolder",
                        "size": "Large",
                    },
                    {
                        "type": "TextBlock",
                        "text": "I'm your AI-powered document intelligence assistant. I can help you find information, identify risks, and discover opportunities in your documents.",
                        "wrap": True,
                    },
                ],
            },
            {
                "type": "Container",
                "separator": True,
                "spacing": "Medium",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": "🚀 Getting Started",
                        "weight": "Bolder",
                    },
                    {
                        "type": "TextBlock",
                        "text": "1. Link your account: `link <tenant-id>`\n2. Ask questions: Just type your question\n3. View insights: Type `insights`",
                        "wrap": True,
                    },
                ],
            },
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "View Help",
                "data": {"action": {"type": "help"}},
            },
        ],
    }

    return CardFactory.adaptive_card(card)


def create_help_card() -> Attachment:
    """Create a help card.

    Returns:
        Adaptive card attachment
    """
    card = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "text": "📚 ASWA Help",
                "weight": "Bolder",
                "size": "Large",
            },
            {
                "type": "Container",
                "separator": True,
                "items": [
                    {
                        "type": "TextBlock",
                        "text": "**Commands:**",
                        "weight": "Bolder",
                    },
                    {
                        "type": "FactSet",
                        "facts": [
                            {"title": "help", "value": "Show this help message"},
                            {"title": "status", "value": "Check system status"},
                            {"title": "link <id>", "value": "Link to ASWA tenant"},
                            {"title": "insights", "value": "View recent insights"},
                            {"title": "insights risks", "value": "View risk insights"},
                        ],
                    },
                ],
            },
            {
                "type": "Container",
                "separator": True,
                "items": [
                    {
                        "type": "TextBlock",
                        "text": "**Examples:**",
                        "weight": "Bolder",
                    },
                    {
                        "type": "TextBlock",
                        "text": "• What are the main risks in the Q4 report?\n• Summarize the financial highlights\n• Compare revenue across regions",
                        "wrap": True,
                    },
                ],
            },
        ],
    }

    return CardFactory.adaptive_card(card)


def create_digest_card(
    digest: dict,
    period: str = "daily",
) -> Attachment:
    """Create a digest summary card.

    Args:
        digest: Digest data
        period: Digest period

    Returns:
        Adaptive card attachment
    """
    sections = []

    for section in digest.get("sections", []):
        section_name = section.get("name", "")
        items = section.get("items", [])

        if items:
            item_texts = []
            for item in items[:3]:
                title = item.get("title", "")
                item_texts.append(f"• {title}")

            sections.append({
                "type": "Container",
                "separator": True,
                "items": [
                    {
                        "type": "TextBlock",
                        "text": section_name,
                        "weight": "Bolder",
                        "size": "Small",
                    },
                    {
                        "type": "TextBlock",
                        "text": "\n".join(item_texts),
                        "wrap": True,
                        "size": "Small",
                    },
                ],
            })

    card = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "text": f"📰 {period.title()} Digest",
                "weight": "Bolder",
                "size": "Large",
            },
            {
                "type": "TextBlock",
                "text": digest.get("summary", "No summary available."),
                "wrap": True,
            },
            *sections,
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "View Weekly",
                "data": {"action": {"type": "digest", "data": {"period": "weekly"}}},
            },
        ],
    }

    return CardFactory.adaptive_card(card)


def create_feedback_card(query_id: str) -> Attachment:
    """Create a detailed feedback card.

    Args:
        query_id: Query identifier

    Returns:
        Adaptive card attachment
    """
    card = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "text": "📝 Provide Feedback",
                "weight": "Bolder",
                "size": "Large",
            },
            {
                "type": "TextBlock",
                "text": "Help us improve by telling us what went wrong.",
                "wrap": True,
            },
            {
                "type": "Input.ChoiceSet",
                "id": "issue_type",
                "label": "What was the issue?",
                "isRequired": True,
                "choices": [
                    {"title": "Incorrect answer", "value": "incorrect"},
                    {"title": "Missing information", "value": "incomplete"},
                    {"title": "Wrong sources cited", "value": "wrong_sources"},
                    {"title": "Confusing response", "value": "confusing"},
                    {"title": "Other", "value": "other"},
                ],
            },
            {
                "type": "Input.Text",
                "id": "feedback_text",
                "label": "Additional details (optional)",
                "isMultiline": True,
                "placeholder": "Tell us more...",
            },
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "Submit Feedback",
                "data": {
                    "action": {
                        "type": "detailed_feedback",
                        "data": {"query_id": query_id},
                    },
                },
            },
        ],
    }

    return CardFactory.adaptive_card(card)


def create_query_form_card() -> Attachment:
    """Create a query input form card.

    Returns:
        Adaptive card attachment
    """
    card = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "text": "🔍 Ask ASWA",
                "weight": "Bolder",
                "size": "Large",
            },
            {
                "type": "Input.Text",
                "id": "query",
                "label": "Your question",
                "isRequired": True,
                "isMultiline": True,
                "placeholder": "What would you like to know?",
            },
            {
                "type": "Input.ChoiceSet",
                "id": "query_type",
                "label": "Query type (optional)",
                "choices": [
                    {"title": "General question", "value": "general"},
                    {"title": "Find risks", "value": "risks"},
                    {"title": "Find opportunities", "value": "opportunities"},
                    {"title": "Summarize", "value": "summary"},
                ],
                "value": "general",
            },
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "Ask",
                "data": {"action": {"type": "query"}},
            },
        ],
    }

    return CardFactory.adaptive_card(card)
```

## Test Requirements

### Create `/services/teams-bot/tests/cards/test_adaptive_cards.py`
```python
import pytest
from aswa_teams.cards.adaptive_cards import (
    create_answer_card,
    create_insights_card,
    create_error_card,
    create_welcome_card,
    create_help_card,
    create_digest_card,
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
```

## Verification

1. Run tests: `cd /services/teams-bot && python -m pytest tests/cards/ -v`
2. Verify imports: `python -c "from aswa_teams.cards import create_answer_card"`
3. Test cards in Teams using the Bot Framework Emulator
