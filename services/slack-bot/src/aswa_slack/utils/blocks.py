from typing import Any


def text_block(text: str, block_type: str = "mrkdwn") -> dict:
    """Create a text block.

    Args:
        text: Block text
        block_type: Text type (mrkdwn or plain_text)

    Returns:
        Slack block
    """
    return {
        "type": "section",
        "text": {
            "type": block_type,
            "text": text,
        }
    }


def header_block(text: str) -> dict:
    """Create a header block.

    Args:
        text: Header text

    Returns:
        Slack block
    """
    return {
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": text,
            "emoji": True,
        }
    }


def divider_block() -> dict:
    """Create a divider block."""
    return {"type": "divider"}


def button_block(
    text: str,
    action_id: str,
    value: str = "",
    style: str | None = None,
) -> dict:
    """Create a button element.

    Args:
        text: Button text
        action_id: Action identifier
        value: Button value
        style: Optional style (primary, danger)

    Returns:
        Button element
    """
    button = {
        "type": "button",
        "text": {
            "type": "plain_text",
            "text": text,
            "emoji": True,
        },
        "action_id": action_id,
        "value": value,
    }

    if style:
        button["style"] = style

    return button


def actions_block(elements: list[dict], block_id: str = "") -> dict:
    """Create an actions block.

    Args:
        elements: List of interactive elements
        block_id: Optional block ID

    Returns:
        Actions block
    """
    block = {
        "type": "actions",
        "elements": elements,
    }

    if block_id:
        block["block_id"] = block_id

    return block


def context_block(elements: list[str]) -> dict:
    """Create a context block.

    Args:
        elements: List of text strings

    Returns:
        Context block
    """
    return {
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": text}
            for text in elements
        ]
    }


def input_block(
    label: str,
    action_id: str,
    placeholder: str = "",
    multiline: bool = False,
    optional: bool = False,
) -> dict:
    """Create an input block.

    Args:
        label: Input label
        action_id: Action identifier
        placeholder: Placeholder text
        multiline: Allow multiline input
        optional: Whether input is optional

    Returns:
        Input block
    """
    return {
        "type": "input",
        "optional": optional,
        "label": {
            "type": "plain_text",
            "text": label,
        },
        "element": {
            "type": "plain_text_input",
            "action_id": action_id,
            "placeholder": {
                "type": "plain_text",
                "text": placeholder,
            },
            "multiline": multiline,
        }
    }


def select_block(
    label: str,
    action_id: str,
    options: list[tuple[str, str]],
    placeholder: str = "Select an option",
) -> dict:
    """Create a select block.

    Args:
        label: Select label
        action_id: Action identifier
        options: List of (text, value) tuples
        placeholder: Placeholder text

    Returns:
        Select block
    """
    return {
        "type": "input",
        "label": {
            "type": "plain_text",
            "text": label,
        },
        "element": {
            "type": "static_select",
            "action_id": action_id,
            "placeholder": {
                "type": "plain_text",
                "text": placeholder,
            },
            "options": [
                {
                    "text": {"type": "plain_text", "text": text},
                    "value": value,
                }
                for text, value in options
            ]
        }
    }


def answer_blocks(
    answer: str,
    citations: list[dict] | None = None,
    query: str | None = None,
) -> list[dict]:
    """Create blocks for displaying an answer.

    Args:
        answer: Answer text
        citations: Optional list of citations
        query: Optional original query

    Returns:
        List of blocks
    """
    blocks = []

    if query:
        blocks.append(context_block([f"*Query:* {query}"]))

    blocks.append(text_block(answer))

    if citations:
        blocks.append(divider_block())
        citation_text = "*Sources:*\n"
        for i, citation in enumerate(citations, 1):
            doc_name = citation.get("document_name", "Unknown")
            page = citation.get("page_number")
            if page:
                citation_text += f"[{i}] {doc_name}, p.{page}\n"
            else:
                citation_text += f"[{i}] {doc_name}\n"

        blocks.append(context_block([citation_text]))

    return blocks


def insight_blocks(
    insights: list[dict],
    insight_type: str = "all",
) -> list[dict]:
    """Create blocks for displaying insights.

    Args:
        insights: List of insights
        insight_type: Type filter label

    Returns:
        List of blocks
    """
    blocks = [
        header_block(f"{insight_type.title()} Insights"),
    ]

    for insight in insights:
        title = insight.get("title", "Untitled")
        description = insight.get("description", "")[:200]
        confidence = insight.get("confidence", 0)

        emoji = "Warning" if insight.get("type") == "risk" else "Insight"

        blocks.append(text_block(
            f"*{title}*\n{description}"
        ))
        blocks.append(context_block([
            f"Confidence: {confidence:.0%}",
            f"Type: {insight.get('type', 'unknown')}",
        ]))
        blocks.append(divider_block())

    return blocks


def error_blocks(message: str, details: str | None = None) -> list[dict]:
    """Create blocks for error display.

    Args:
        message: Error message
        details: Optional details

    Returns:
        List of blocks
    """
    blocks = [
        text_block(f"*Error:* {message}")
    ]

    if details:
        blocks.append(context_block([details]))

    return blocks


def loading_blocks(message: str = "Processing your request...") -> list[dict]:
    """Create blocks for loading state.

    Args:
        message: Loading message

    Returns:
        List of blocks
    """
    return [
        text_block(f"{message}")
    ]
