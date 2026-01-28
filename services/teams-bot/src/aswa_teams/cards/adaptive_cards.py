"""Adaptive Card templates for Teams bot."""
from typing import Any
from botbuilder.schema import Attachment


def create_answer_card(
    query: str,
    answer: str,
    citations: list[dict[str, Any]],
    confidence: float,
    query_id: str,
) -> Attachment:
    """Create an answer card.

    Args:
        query: Original query
        answer: Answer text
        citations: List of citations
        confidence: Confidence score
        query_id: Query identifier

    Returns:
        Attachment with adaptive card
    """
    confidence_text = _format_confidence(confidence)

    body = [
        {
            "type": "TextBlock",
            "text": "Answer",
            "weight": "bolder",
            "size": "medium",
        },
        {
            "type": "TextBlock",
            "text": answer,
            "wrap": True,
        },
    ]

    if citations:
        body.append({
            "type": "TextBlock",
            "text": "Sources",
            "weight": "bolder",
            "size": "small",
            "spacing": "medium",
        })

        for i, citation in enumerate(citations[:5], 1):
            title = citation.get("title", f"Source {i}")
            body.append({
                "type": "TextBlock",
                "text": f"{i}. {title}",
                "size": "small",
                "wrap": True,
            })

    body.append({
        "type": "TextBlock",
        "text": f"Confidence: {confidence_text}",
        "size": "small",
        "color": "accent",
        "spacing": "medium",
    })

    card = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": body,
        "actions": [
            {
                "type": "Action.Execute",
                "title": "Helpful",
                "verb": "feedback",
                "data": {
                    "action": {"type": "feedback", "data": {"query_id": query_id, "feedback": "helpful"}},
                },
            },
            {
                "type": "Action.Execute",
                "title": "Not Helpful",
                "verb": "feedback",
                "data": {
                    "action": {"type": "feedback", "data": {"query_id": query_id, "feedback": "not_helpful"}},
                },
            },
        ],
    }

    return Attachment(
        content_type="application/vnd.microsoft.card.adaptive",
        content=card,
    )


def create_insights_card(insights: list[dict[str, Any]], insight_type: str) -> Attachment:
    """Create an insights card.

    Args:
        insights: List of insights
        insight_type: Type of insights

    Returns:
        Attachment with adaptive card
    """
    title = f"{insight_type.title()} Insights" if insight_type != "all" else "All Insights"

    body = [
        {
            "type": "TextBlock",
            "text": title,
            "weight": "bolder",
            "size": "medium",
        },
    ]

    if not insights:
        body.append({
            "type": "TextBlock",
            "text": "No insights found.",
            "wrap": True,
        })
    else:
        for insight in insights[:10]:
            insight_title = insight.get("title", "Untitled")
            description = insight.get("description", "")
            confidence = insight.get("confidence", 0)

            body.extend([
                {
                    "type": "TextBlock",
                    "text": insight_title,
                    "weight": "bolder",
                    "size": "small",
                    "spacing": "medium",
                },
                {
                    "type": "TextBlock",
                    "text": description[:200],
                    "wrap": True,
                    "size": "small",
                },
                {
                    "type": "TextBlock",
                    "text": f"Confidence: {_format_confidence(confidence)}",
                    "size": "small",
                    "color": "accent",
                },
            ])

    card = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": body,
    }

    return Attachment(
        content_type="application/vnd.microsoft.card.adaptive",
        content=card,
    )


def create_error_card(title: str, message: str) -> Attachment:
    """Create an error card.

    Args:
        title: Error title
        message: Error message

    Returns:
        Attachment with adaptive card
    """
    card = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "text": f"❌ {title}",
                "weight": "bolder",
                "color": "attention",
            },
            {
                "type": "TextBlock",
                "text": message,
                "wrap": True,
            },
        ],
    }

    return Attachment(
        content_type="application/vnd.microsoft.card.adaptive",
        content=card,
    )


def create_welcome_card(bot_name: str) -> Attachment:
    """Create a welcome card.

    Args:
        bot_name: Bot display name

    Returns:
        Attachment with adaptive card
    """
    card = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "text": f"Welcome to {bot_name}!",
                "weight": "bolder",
                "size": "large",
            },
            {
                "type": "TextBlock",
                "text": "I'm your AI-powered document intelligence assistant. Ask me questions about your documents!",
                "wrap": True,
            },
            {
                "type": "TextBlock",
                "text": "Getting Started",
                "weight": "bolder",
                "spacing": "medium",
            },
            {
                "type": "TextBlock",
                "text": "1. Link your account: `link <tenant-id>`\n2. Ask questions about your documents\n3. View insights: `insights` or `insights risks`",
                "wrap": True,
            },
            {
                "type": "TextBlock",
                "text": "Type `help` for more commands.",
                "size": "small",
                "spacing": "medium",
            },
        ],
    }

    return Attachment(
        content_type="application/vnd.microsoft.card.adaptive",
        content=card,
    )


def create_help_card() -> Attachment:
    """Create a help card.

    Returns:
        Attachment with adaptive card
    """
    card = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "text": "ASWA Help",
                "weight": "bolder",
                "size": "large",
            },
            {
                "type": "TextBlock",
                "text": "Commands",
                "weight": "bolder",
                "spacing": "medium",
            },
            {
                "type": "FactSet",
                "facts": [
                    {"title": "help", "value": "Show this help message"},
                    {"title": "status", "value": "Check service status"},
                    {"title": "link <tenant-id>", "value": "Link to ASWA tenant"},
                    {"title": "insights", "value": "View all insights"},
                    {"title": "insights <type>", "value": "View insights by type (risks, opportunities, trends)"},
                ],
            },
            {
                "type": "TextBlock",
                "text": "Examples",
                "weight": "bolder",
                "spacing": "medium",
            },
            {
                "type": "TextBlock",
                "text": "• What are the main risks in Q4 report?\n• Summarize the financial highlights\n• Compare revenue across regions",
                "wrap": True,
            },
        ],
    }

    return Attachment(
        content_type="application/vnd.microsoft.card.adaptive",
        content=card,
    )


def _format_confidence(confidence: float) -> str:
    """Format confidence score.

    Args:
        confidence: Confidence value (0-1)

    Returns:
        Formatted string
    """
    percentage = int(confidence * 100)

    if percentage >= 80:
        return f"High ({percentage}%)"
    elif percentage >= 50:
        return f"Medium ({percentage}%)"
    else:
        return f"Low ({percentage}%)"
