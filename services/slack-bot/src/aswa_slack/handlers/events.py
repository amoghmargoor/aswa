"""Event handlers for ASWA Slack bot."""
from slack_bolt.async_app import AsyncApp
import structlog
import re

from ..utils import text_block, answer_blocks, error_blocks, loading_blocks

logger = structlog.get_logger()


def register_events(app: AsyncApp) -> None:
    """Register event handlers.

    Args:
        app: Slack Bolt app
    """

    @app.event("app_mention")
    async def handle_app_mention(event, say, client):
        """Handle when bot is mentioned."""
        user_id = event.get("user")
        channel = event.get("channel")
        text = event.get("text", "")
        thread_ts = event.get("thread_ts") or event.get("ts")

        # Remove bot mention from text
        text = re.sub(r"<@[A-Z0-9]+>", "", text).strip()

        logger.info(
            "App mentioned",
            user_id=user_id,
            channel=channel,
            text=text[:50] if text else "",
        )

        if not text:
            await say(
                blocks=[text_block("Hi! How can I help you? Ask me a question about your documents.")],
                thread_ts=thread_ts,
            )
            return

        # Treat mention as a query
        await _handle_mention_query(say, app, user_id, text, thread_ts)

    @app.event("message")
    async def handle_message(event, say, client):
        """Handle direct messages to the bot."""
        # Only handle DMs (im channel type)
        channel_type = event.get("channel_type")
        if channel_type != "im":
            return

        # Ignore bot messages
        if event.get("bot_id"):
            return

        user_id = event.get("user")
        text = event.get("text", "").strip()
        thread_ts = event.get("thread_ts") or event.get("ts")

        if not text:
            return

        logger.info(
            "DM received",
            user_id=user_id,
            text=text[:50] if text else "",
        )

        # Handle as query
        await _handle_mention_query(say, app, user_id, text, thread_ts)

    @app.event("app_home_opened")
    async def handle_app_home_opened(client, event):
        """Handle App Home tab opened."""
        user_id = event.get("user")

        logger.info("App Home opened", user_id=user_id)

        try:
            await client.views_publish(
                user_id=user_id,
                view=_build_home_view(),
            )
        except Exception as e:
            logger.error("Failed to publish home view", error=str(e))

    @app.event("team_join")
    async def handle_team_join(event, client):
        """Handle new team member joining."""
        user_id = event.get("user", {}).get("id")

        if user_id:
            logger.info("New team member", user_id=user_id)
            # Could send welcome DM here

    logger.info("Event handlers registered")


async def _handle_mention_query(say, app: AsyncApp, user_id: str, query: str, thread_ts: str):
    """Handle a query from mention or DM."""
    # Show loading
    loading_msg = await say(
        blocks=loading_blocks("Thinking..."),
        thread_ts=thread_ts,
    )

    try:
        query_client = app._query_client

        response = await query_client.query(
            tenant_id="00000000-0000-0000-0000-000000000000",  # Placeholder
            query=query,
            user_id=user_id,
        )

        answer = response.get("answer", "I couldn't find an answer to that.")
        citations = response.get("citations", [])

        await say(
            blocks=answer_blocks(answer, citations),
            thread_ts=thread_ts,
        )

    except Exception as e:
        logger.error("Query failed", error=str(e))
        await say(
            blocks=error_blocks("Sorry, I encountered an error processing your request."),
            thread_ts=thread_ts,
        )


def _build_home_view() -> dict:
    """Build the App Home view."""
    return {
        "type": "home",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "Welcome to ASWA",
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "ASWA helps you get insights from your documents using AI."
                }
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Quick Actions*"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Ask a Question"},
                        "action_id": "open_query_modal",
                        "style": "primary",
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View Insights"},
                        "action_id": "view_insights",
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Daily Digest"},
                        "action_id": "view_digest",
                    },
                ]
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Getting Started*\n\n"
                           "1. Mention @ASWA in any channel with a question\n"
                           "2. Use `/aswa` command for detailed queries\n"
                           "3. Send me a direct message anytime"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "Need help? Use `/aswa help` for available commands."
                    }
                ]
            }
        ]
    }
