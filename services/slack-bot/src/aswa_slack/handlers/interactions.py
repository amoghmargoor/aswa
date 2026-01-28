"""Interactive component handlers for ASWA Slack bot."""
from slack_bolt.async_app import AsyncApp
import structlog

from ..utils import text_block, input_block, answer_blocks, error_blocks, loading_blocks

logger = structlog.get_logger()


def register_interactions(app: AsyncApp) -> None:
    """Register interaction handlers.

    Args:
        app: Slack Bolt app
    """

    @app.action("open_query_modal")
    async def handle_open_query_modal(ack, body, client):
        """Open query modal from button click."""
        await ack()

        trigger_id = body.get("trigger_id")

        await client.views_open(
            trigger_id=trigger_id,
            view=_build_query_modal(),
        )

    @app.view("query_submission")
    async def handle_query_submission(ack, body, client, view):
        """Handle query modal submission."""
        await ack()

        user_id = body.get("user", {}).get("id")
        values = view.get("state", {}).get("values", {})

        # Extract query from modal
        query_input = values.get("query_block", {}).get("query_input", {})
        query = query_input.get("value", "").strip()

        if not query:
            return

        logger.info("Query submitted via modal", user_id=user_id)

        try:
            query_client = app._query_client

            response = await query_client.query(
                tenant_id="00000000-0000-0000-0000-000000000000",  # Placeholder
                query=query,
                user_id=user_id,
            )

            answer = response.get("answer", "No answer found.")
            citations = response.get("citations", [])

            # Send DM with results
            await client.chat_postMessage(
                channel=user_id,
                blocks=answer_blocks(answer, citations, query),
            )

        except Exception as e:
            logger.error("Query failed", error=str(e))
            await client.chat_postMessage(
                channel=user_id,
                blocks=error_blocks("Failed to process your query", str(e)),
            )

    @app.action("view_insights")
    async def handle_view_insights(ack, body, client):
        """Handle view insights button."""
        await ack()

        user_id = body.get("user", {}).get("id")

        try:
            query_client = app._query_client

            response = await query_client.get_insights(
                tenant_id="00000000-0000-0000-0000-000000000000",  # Placeholder
                limit=5,
            )

            insights = response.get("insights", [])

            if not insights:
                await client.chat_postMessage(
                    channel=user_id,
                    blocks=[text_block("No recent insights available.")]
                )
                return

            from ..utils import insight_blocks
            await client.chat_postMessage(
                channel=user_id,
                blocks=insight_blocks(insights, "Recent"),
            )

        except Exception as e:
            logger.error("Get insights failed", error=str(e))
            await client.chat_postMessage(
                channel=user_id,
                blocks=error_blocks("Failed to get insights"),
            )

    @app.action("view_digest")
    async def handle_view_digest(ack, body, client):
        """Handle view digest button."""
        await ack()

        user_id = body.get("user", {}).get("id")

        try:
            query_client = app._query_client

            response = await query_client.get_digest(
                tenant_id="00000000-0000-0000-0000-000000000000",  # Placeholder
                period="daily",
            )

            digest = response.get("content", "No digest available.")

            await client.chat_postMessage(
                channel=user_id,
                blocks=[
                    {"type": "header", "text": {"type": "plain_text", "text": "Daily Digest"}},
                    text_block(digest),
                ]
            )

        except Exception as e:
            logger.error("Get digest failed", error=str(e))
            await client.chat_postMessage(
                channel=user_id,
                blocks=error_blocks("Failed to get digest"),
            )

    @app.action("feedback_helpful")
    async def handle_feedback_helpful(ack, body, client):
        """Handle helpful feedback button."""
        await ack()

        user_id = body.get("user", {}).get("id")
        message_ts = body.get("message", {}).get("ts")
        channel = body.get("channel", {}).get("id")

        logger.info("Positive feedback received", user_id=user_id)

        # Update message to show feedback received
        try:
            original_blocks = body.get("message", {}).get("blocks", [])
            # Remove action buttons, add thank you
            updated_blocks = [b for b in original_blocks if b.get("type") != "actions"]
            updated_blocks.append({
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": "Thanks for your feedback!"}]
            })

            await client.chat_update(
                channel=channel,
                ts=message_ts,
                blocks=updated_blocks,
            )
        except Exception as e:
            logger.error("Failed to update feedback", error=str(e))

    @app.action("feedback_not_helpful")
    async def handle_feedback_not_helpful(ack, body, client):
        """Handle not helpful feedback button."""
        await ack()

        user_id = body.get("user", {}).get("id")
        trigger_id = body.get("trigger_id")

        logger.info("Negative feedback received", user_id=user_id)

        # Open modal for detailed feedback
        await client.views_open(
            trigger_id=trigger_id,
            view=_build_feedback_modal(),
        )

    @app.view("feedback_submission")
    async def handle_feedback_submission(ack, body, client, view):
        """Handle feedback modal submission."""
        await ack()

        user_id = body.get("user", {}).get("id")
        values = view.get("state", {}).get("values", {})

        feedback_input = values.get("feedback_block", {}).get("feedback_input", {})
        feedback = feedback_input.get("value", "")

        logger.info("Detailed feedback received", user_id=user_id, feedback=feedback[:100])

        # Send confirmation
        await client.chat_postMessage(
            channel=user_id,
            text="Thank you for your feedback! We'll use it to improve ASWA."
        )

    logger.info("Interaction handlers registered")


def _build_query_modal() -> dict:
    """Build the query modal view."""
    return {
        "type": "modal",
        "callback_id": "query_submission",
        "title": {"type": "plain_text", "text": "Ask ASWA"},
        "submit": {"type": "plain_text", "text": "Submit"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": "query_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "query_input",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "What would you like to know about your documents?"
                    }
                },
                "label": {"type": "plain_text", "text": "Your Question"}
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "Tip: Be specific for better results."
                    }
                ]
            }
        ]
    }


def _build_feedback_modal() -> dict:
    """Build the feedback modal view."""
    return {
        "type": "modal",
        "callback_id": "feedback_submission",
        "title": {"type": "plain_text", "text": "Provide Feedback"},
        "submit": {"type": "plain_text", "text": "Submit"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "We're sorry the response wasn't helpful. Please tell us how we can improve."
                }
            },
            {
                "type": "input",
                "block_id": "feedback_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "feedback_input",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "What was wrong with the response? What did you expect?"
                    }
                },
                "label": {"type": "plain_text", "text": "Your Feedback"}
            }
        ]
    }
