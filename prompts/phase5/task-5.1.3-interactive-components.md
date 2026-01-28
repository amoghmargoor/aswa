# Task 5.1.3: Slack Bot - Interactive Components

## Context

You are working on the ASWA Slack bot at `/services/slack-bot/`. Slash commands are complete (Task 5.1.2). Now we need to implement interactive components like buttons, modals, and menus.

## Objective

Create interactive component handlers that:
1. Handle button clicks and actions
2. Implement modal dialogs for complex inputs
3. Support select menus for filtering
4. Provide feedback collection
5. Handle message shortcuts

## Requirements

### 1. Create `/services/slack-bot/src/aswa_slack/handlers/interactions.py`
```python
from typing import Any
from uuid import UUID
import structlog

from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient

from ..services.query_client import QueryClient
from ..services.user_service import UserService
from ..utils.blocks import (
    text_block,
    header_block,
    divider_block,
    button_block,
    actions_block,
    context_block,
    input_block,
    select_block,
    answer_blocks,
    insight_blocks,
    error_blocks,
)

logger = structlog.get_logger()


def register_interactions(app: AsyncApp) -> None:
    """Register interaction handlers.

    Args:
        app: Slack Bolt app
    """

    # Button Actions
    @app.action("feedback_helpful")
    async def handle_feedback_helpful(ack, body, client: AsyncWebClient):
        """Handle helpful feedback button."""
        await ack()

        user_id = body.get("user", {}).get("id", "")
        query_id = body.get("actions", [{}])[0].get("value", "")

        logger.info("Helpful feedback received", user_id=user_id, query_id=query_id)

        # Record feedback
        await record_feedback(query_id, "helpful", user_id, app)

        # Update message to show feedback received
        await update_message_with_thanks(body, client, "Thanks for your feedback! 👍")

    @app.action("feedback_not_helpful")
    async def handle_feedback_not_helpful(ack, body, client: AsyncWebClient):
        """Handle not helpful feedback button."""
        await ack()

        user_id = body.get("user", {}).get("id", "")
        query_id = body.get("actions", [{}])[0].get("value", "")

        # Open modal for detailed feedback
        await client.views_open(
            trigger_id=body["trigger_id"],
            view=get_feedback_modal(query_id),
        )

    @app.action("refine_query")
    async def handle_refine_query(ack, body, client: AsyncWebClient):
        """Handle refine query button."""
        await ack()

        original_query = body.get("actions", [{}])[0].get("value", "")

        await client.views_open(
            trigger_id=body["trigger_id"],
            view=get_refine_modal(original_query),
        )

    @app.action("view_insights")
    async def handle_view_insights(ack, body, say, client: AsyncWebClient):
        """Handle view insights button."""
        await ack()

        insight_type = body.get("actions", [{}])[0].get("value", "all")
        user_id = body.get("user", {}).get("id", "")
        team_id = body.get("team", {}).get("id", "")

        try:
            user_service = UserService(app._settings.redis_url)
            user = await user_service.get_or_create_user(user_id, team_id)

            if not user.is_linked:
                return

            query_client: QueryClient = app._query_client
            types = [insight_type] if insight_type != "all" else None

            result = await query_client.get_insights(
                tenant_id=user.aswa_tenant_id,
                insight_types=types,
                limit=10,
            )

            blocks = insight_blocks(result.get("insights", []), insight_type)

            await client.chat_postMessage(
                channel=body["channel"]["id"],
                blocks=blocks,
            )

        except Exception as e:
            logger.error("View insights failed", error=str(e))

    @app.action("view_document")
    async def handle_view_document(ack, body, client: AsyncWebClient):
        """Handle view document button."""
        await ack()

        document_id = body.get("actions", [{}])[0].get("value", "")
        user_id = body.get("user", {}).get("id", "")

        # Open document details modal
        await client.views_open(
            trigger_id=body["trigger_id"],
            view=get_document_modal(document_id),
        )

    @app.action("filter_insights")
    async def handle_filter_insights(ack, body, client: AsyncWebClient):
        """Handle insight filter selection."""
        await ack()

        selected = body.get("actions", [{}])[0].get("selected_option", {})
        filter_value = selected.get("value", "all")

        # Would update the message with filtered results
        logger.info("Insights filtered", filter=filter_value)

    @app.action("dismiss_message")
    async def handle_dismiss(ack, body, client: AsyncWebClient):
        """Handle dismiss button."""
        await ack()

        try:
            await client.chat_delete(
                channel=body["channel"]["id"],
                ts=body["message"]["ts"],
            )
        except Exception as e:
            logger.warning("Could not delete message", error=str(e))

    # Modal Submissions
    @app.view("feedback_modal")
    async def handle_feedback_modal(ack, body, client: AsyncWebClient, view):
        """Handle feedback modal submission."""
        await ack()

        user_id = body.get("user", {}).get("id", "")
        values = view.get("state", {}).get("values", {})

        # Extract values from modal
        query_id = view.get("private_metadata", "")
        feedback_text = values.get("feedback_block", {}).get("feedback_input", {}).get("value", "")
        issue_type = values.get("issue_block", {}).get("issue_select", {}).get("selected_option", {}).get("value", "")

        logger.info(
            "Detailed feedback received",
            user_id=user_id,
            query_id=query_id,
            issue_type=issue_type,
        )

        # Record detailed feedback
        await record_detailed_feedback(
            query_id=query_id,
            user_id=user_id,
            feedback_text=feedback_text,
            issue_type=issue_type,
            app=app,
        )

        # Send confirmation
        try:
            await client.chat_postMessage(
                channel=user_id,
                text="Thank you for your detailed feedback! We'll use it to improve ASWA.",
            )
        except Exception:
            pass

    @app.view("refine_modal")
    async def handle_refine_modal(ack, body, client: AsyncWebClient, view):
        """Handle refine query modal submission."""
        await ack()

        user_id = body.get("user", {}).get("id", "")
        team_id = body.get("team", {}).get("id", "")
        values = view.get("state", {}).get("values", {})

        refined_query = values.get("query_block", {}).get("query_input", {}).get("value", "")

        if refined_query:
            # Process the refined query
            user_service = UserService(app._settings.redis_url)
            user = await user_service.get_or_create_user(user_id, team_id)

            if user.is_linked:
                query_client: QueryClient = app._query_client
                result = await query_client.query(
                    tenant_id=user.aswa_tenant_id,
                    query=refined_query,
                    user_id=user_id,
                )

                blocks = answer_blocks(
                    result.get("answer", ""),
                    result.get("citations", []),
                    query=refined_query,
                )

                await client.chat_postMessage(
                    channel=user_id,
                    blocks=blocks,
                )

    @app.view("query_modal")
    async def handle_query_modal(ack, body, client: AsyncWebClient, view):
        """Handle query modal submission."""
        await ack()

        user_id = body.get("user", {}).get("id", "")
        team_id = body.get("team", {}).get("id", "")
        values = view.get("state", {}).get("values", {})

        query = values.get("query_block", {}).get("query_input", {}).get("value", "")

        if query:
            user_service = UserService(app._settings.redis_url)
            user = await user_service.get_or_create_user(user_id, team_id)

            if user.is_linked:
                query_client: QueryClient = app._query_client

                result = await query_client.query(
                    tenant_id=user.aswa_tenant_id,
                    query=query,
                    user_id=user_id,
                )

                blocks = answer_blocks(
                    result.get("answer", ""),
                    result.get("citations", []),
                    query=query,
                )

                await client.chat_postMessage(
                    channel=user_id,
                    blocks=blocks,
                )

    # Message Shortcuts
    @app.shortcut("ask_about_message")
    async def handle_ask_about_message(ack, shortcut, client: AsyncWebClient):
        """Handle 'Ask ASWA about this' message shortcut."""
        await ack()

        message_text = shortcut.get("message", {}).get("text", "")

        await client.views_open(
            trigger_id=shortcut["trigger_id"],
            view=get_ask_about_modal(message_text),
        )

    @app.shortcut("summarize_thread")
    async def handle_summarize_thread(ack, shortcut, client: AsyncWebClient):
        """Handle 'Summarize thread' message shortcut."""
        await ack()

        channel_id = shortcut.get("channel", {}).get("id", "")
        thread_ts = shortcut.get("message", {}).get("thread_ts") or shortcut.get("message", {}).get("ts", "")
        user_id = shortcut.get("user", {}).get("id", "")

        try:
            # Get thread messages
            result = await client.conversations_replies(
                channel=channel_id,
                ts=thread_ts,
            )

            messages = result.get("messages", [])
            thread_text = "\n".join(m.get("text", "") for m in messages)

            # Summarize using query service
            # This would call the query service for summarization
            summary = f"Thread summary ({len(messages)} messages): ..."

            await client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text=f"📝 *Thread Summary:*\n{summary}",
            )

        except Exception as e:
            logger.error("Summarize thread failed", error=str(e))


async def record_feedback(
    query_id: str,
    feedback_type: str,
    user_id: str,
    app: AsyncApp,
) -> None:
    """Record simple feedback.

    Args:
        query_id: Query identifier
        feedback_type: Type of feedback
        user_id: User who gave feedback
        app: Bolt app
    """
    # Would send to analytics/feedback service
    logger.info(
        "Feedback recorded",
        query_id=query_id,
        feedback_type=feedback_type,
        user_id=user_id,
    )


async def record_detailed_feedback(
    query_id: str,
    user_id: str,
    feedback_text: str,
    issue_type: str,
    app: AsyncApp,
) -> None:
    """Record detailed feedback.

    Args:
        query_id: Query identifier
        user_id: User who gave feedback
        feedback_text: Detailed feedback
        issue_type: Type of issue
        app: Bolt app
    """
    logger.info(
        "Detailed feedback recorded",
        query_id=query_id,
        user_id=user_id,
        issue_type=issue_type,
        feedback_length=len(feedback_text),
    )


async def update_message_with_thanks(
    body: dict,
    client: AsyncWebClient,
    thanks_message: str,
) -> None:
    """Update message to show feedback thanks.

    Args:
        body: Slack event body
        client: Slack client
        thanks_message: Thanks message
    """
    try:
        channel_id = body["channel"]["id"]
        message_ts = body["message"]["ts"]
        original_blocks = body.get("message", {}).get("blocks", [])

        # Remove action buttons and add thanks
        new_blocks = [b for b in original_blocks if b.get("type") != "actions"]
        new_blocks.append(context_block([thanks_message]))

        await client.chat_update(
            channel=channel_id,
            ts=message_ts,
            blocks=new_blocks,
        )
    except Exception as e:
        logger.warning("Could not update message", error=str(e))


def get_feedback_modal(query_id: str) -> dict:
    """Get feedback modal view.

    Args:
        query_id: Query identifier

    Returns:
        Modal view definition
    """
    return {
        "type": "modal",
        "callback_id": "feedback_modal",
        "private_metadata": query_id,
        "title": {"type": "plain_text", "text": "Provide Feedback"},
        "submit": {"type": "plain_text", "text": "Submit"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Help us improve by telling us what went wrong.",
                },
            },
            {
                "type": "input",
                "block_id": "issue_block",
                "label": {"type": "plain_text", "text": "What was the issue?"},
                "element": {
                    "type": "static_select",
                    "action_id": "issue_select",
                    "placeholder": {"type": "plain_text", "text": "Select an issue"},
                    "options": [
                        {"text": {"type": "plain_text", "text": "Incorrect answer"}, "value": "incorrect"},
                        {"text": {"type": "plain_text", "text": "Missing information"}, "value": "incomplete"},
                        {"text": {"type": "plain_text", "text": "Wrong sources cited"}, "value": "wrong_sources"},
                        {"text": {"type": "plain_text", "text": "Confusing response"}, "value": "confusing"},
                        {"text": {"type": "plain_text", "text": "Other"}, "value": "other"},
                    ],
                },
            },
            {
                "type": "input",
                "block_id": "feedback_block",
                "optional": True,
                "label": {"type": "plain_text", "text": "Additional details"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "feedback_input",
                    "multiline": True,
                    "placeholder": {"type": "plain_text", "text": "Tell us more..."},
                },
            },
        ],
    }


def get_refine_modal(original_query: str) -> dict:
    """Get refine query modal view.

    Args:
        original_query: Original query to refine

    Returns:
        Modal view definition
    """
    return {
        "type": "modal",
        "callback_id": "refine_modal",
        "title": {"type": "plain_text", "text": "Refine Query"},
        "submit": {"type": "plain_text", "text": "Ask"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Original query:* {original_query}",
                },
            },
            {
                "type": "input",
                "block_id": "query_block",
                "label": {"type": "plain_text", "text": "Refined query"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "query_input",
                    "initial_value": original_query,
                    "multiline": True,
                    "placeholder": {"type": "plain_text", "text": "Refine your question..."},
                },
            },
        ],
    }


def get_document_modal(document_id: str) -> dict:
    """Get document details modal.

    Args:
        document_id: Document identifier

    Returns:
        Modal view definition
    """
    return {
        "type": "modal",
        "callback_id": "document_modal",
        "title": {"type": "plain_text", "text": "Document Details"},
        "close": {"type": "plain_text", "text": "Close"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Document ID:* `{document_id}`",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "_Loading document details..._",
                },
            },
        ],
    }


def get_ask_about_modal(message_text: str) -> dict:
    """Get ask about message modal.

    Args:
        message_text: Message to ask about

    Returns:
        Modal view definition
    """
    truncated = message_text[:500] + "..." if len(message_text) > 500 else message_text

    return {
        "type": "modal",
        "callback_id": "query_modal",
        "title": {"type": "plain_text", "text": "Ask ASWA"},
        "submit": {"type": "plain_text", "text": "Ask"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Message context:*\n> {truncated}",
                },
            },
            {"type": "divider"},
            {
                "type": "input",
                "block_id": "query_block",
                "label": {"type": "plain_text", "text": "What would you like to know?"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "query_input",
                    "multiline": True,
                    "placeholder": {"type": "plain_text", "text": "Ask a question about this message..."},
                },
            },
        ],
    }
```

## Test Requirements

### Create `/services/slack-bot/tests/handlers/test_interactions.py`
```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aswa_slack.handlers.interactions import (
    get_feedback_modal,
    get_refine_modal,
    get_document_modal,
    get_ask_about_modal,
    record_feedback,
    update_message_with_thanks,
)


class TestModalViews:
    def test_get_feedback_modal(self):
        """Test feedback modal generation."""
        modal = get_feedback_modal("query-123")

        assert modal["type"] == "modal"
        assert modal["callback_id"] == "feedback_modal"
        assert modal["private_metadata"] == "query-123"
        assert len(modal["blocks"]) > 0

    def test_get_refine_modal(self):
        """Test refine modal generation."""
        modal = get_refine_modal("What are the risks?")

        assert modal["type"] == "modal"
        assert modal["callback_id"] == "refine_modal"
        assert "risks" in str(modal["blocks"])

    def test_get_document_modal(self):
        """Test document modal generation."""
        modal = get_document_modal("doc-456")

        assert modal["type"] == "modal"
        assert "doc-456" in str(modal["blocks"])

    def test_get_ask_about_modal(self):
        """Test ask about modal generation."""
        modal = get_ask_about_modal("This is a test message")

        assert modal["type"] == "modal"
        assert modal["callback_id"] == "query_modal"

    def test_get_ask_about_modal_truncates_long_text(self):
        """Test that long messages are truncated."""
        long_message = "x" * 1000
        modal = get_ask_about_modal(long_message)

        # Should be truncated
        block_text = str(modal["blocks"])
        assert "..." in block_text


class TestFeedbackRecording:
    @pytest.mark.asyncio
    async def test_record_feedback(self):
        """Test feedback recording."""
        mock_app = MagicMock()

        # Should not raise
        await record_feedback(
            query_id="query-123",
            feedback_type="helpful",
            user_id="U123",
            app=mock_app,
        )


class TestMessageUpdate:
    @pytest.mark.asyncio
    async def test_update_message_with_thanks(self):
        """Test updating message with thanks."""
        mock_client = AsyncMock()
        mock_client.chat_update = AsyncMock()

        body = {
            "channel": {"id": "C123"},
            "message": {
                "ts": "123.456",
                "blocks": [
                    {"type": "section", "text": {"type": "mrkdwn", "text": "Answer"}},
                    {"type": "actions", "elements": []},
                ],
            },
        }

        await update_message_with_thanks(body, mock_client, "Thanks!")

        mock_client.chat_update.assert_called_once()
        call_kwargs = mock_client.chat_update.call_args.kwargs
        assert call_kwargs["channel"] == "C123"
        assert call_kwargs["ts"] == "123.456"

        # Actions should be removed
        blocks = call_kwargs["blocks"]
        assert not any(b.get("type") == "actions" for b in blocks)
```

## Verification

1. Run tests: `cd /services/slack-bot && python -m pytest tests/handlers/test_interactions.py -v`
2. Verify imports: `python -c "from aswa_slack.handlers.interactions import register_interactions"`
3. Test modals and buttons in Slack workspace
