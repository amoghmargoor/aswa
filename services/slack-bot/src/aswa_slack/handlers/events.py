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
    answer_blocks,
    error_blocks,
    loading_blocks,
)
from ..utils.formatting import format_confidence

logger = structlog.get_logger()


def register_events(app: AsyncApp) -> None:
    """Register event handlers.

    Args:
        app: Slack Bolt app
    """

    @app.event("app_mention")
    async def handle_app_mention(event, say, client: AsyncWebClient):
        """Handle when bot is mentioned in a channel.

        Args:
            event: Slack event
            say: Say function
            client: Slack client
        """
        user_id = event.get("user", "")
        channel_id = event.get("channel", "")
        text = event.get("text", "")
        thread_ts = event.get("thread_ts") or event.get("ts")
        team_id = event.get("team", "")

        # Remove bot mention from text
        # Format: <@BOTID> query text
        import re
        clean_text = re.sub(r'<@[A-Z0-9]+>', '', text).strip()

        if not clean_text:
            await say(
                text="Hi! How can I help you? Try asking a question about your documents.",
                thread_ts=thread_ts,
            )
            return

        logger.info(
            "App mention received",
            user_id=user_id,
            channel_id=channel_id,
            text=clean_text[:50],
        )

        await process_mention_query(
            query=clean_text,
            user_id=user_id,
            team_id=team_id,
            channel_id=channel_id,
            thread_ts=thread_ts,
            say=say,
            client=client,
            app=app,
        )

    @app.event("message")
    async def handle_message(event, say, client: AsyncWebClient):
        """Handle direct messages to the bot.

        Args:
            event: Slack event
            say: Say function
            client: Slack client
        """
        # Ignore bot messages
        if event.get("bot_id"):
            return

        # Only handle DMs
        channel_type = event.get("channel_type", "")
        if channel_type != "im":
            return

        user_id = event.get("user", "")
        text = event.get("text", "").strip()
        team_id = event.get("team", "")

        if not text:
            return

        logger.info(
            "DM received",
            user_id=user_id,
            text=text[:50],
        )

        # Handle special commands
        if text.lower() == "help":
            await say(blocks=get_dm_help_blocks())
            return

        if text.lower() == "status":
            await handle_dm_status(say, app)
            return

        # Process as query
        await process_dm_query(
            query=text,
            user_id=user_id,
            team_id=team_id,
            say=say,
            client=client,
            app=app,
        )

    @app.event("app_home_opened")
    async def handle_home_opened(event, client: AsyncWebClient):
        """Handle when user opens the app home tab.

        Args:
            event: Slack event
            client: Slack client
        """
        user_id = event.get("user", "")
        team_id = event.get("view", {}).get("team_id", "")

        logger.info("Home tab opened", user_id=user_id)

        try:
            home_view = await build_home_view(user_id, team_id, app)

            await client.views_publish(
                user_id=user_id,
                view=home_view,
            )

        except Exception as e:
            logger.error("Failed to publish home view", error=str(e))

    @app.event("member_joined_channel")
    async def handle_member_joined(event, say, client: AsyncWebClient):
        """Handle when bot joins a channel.

        Args:
            event: Slack event
            say: Say function
            client: Slack client
        """
        user_id = event.get("user", "")

        # Check if it's the bot joining
        try:
            auth_result = await client.auth_test()
            bot_user_id = auth_result.get("user_id", "")

            if user_id == bot_user_id:
                logger.info("Bot joined channel", channel=event.get("channel"))

                await say(
                    text="Hi! I'm ASWA, your AI document assistant. "
                         "Mention me with a question to get started, or type `/aswa help` for more info.",
                )

        except Exception as e:
            logger.error("Failed to handle channel join", error=str(e))

    @app.event("file_shared")
    async def handle_file_shared(event, client: AsyncWebClient):
        """Handle when a file is shared.

        Args:
            event: Slack event
            client: Slack client
        """
        file_id = event.get("file_id", "")
        user_id = event.get("user_id", "")
        channel_id = event.get("channel_id", "")

        logger.info(
            "File shared",
            file_id=file_id,
            user_id=user_id,
            channel_id=channel_id,
        )

        # Could trigger document ingestion workflow
        # For now, just log

    @app.event("reaction_added")
    async def handle_reaction_added(event, client: AsyncWebClient):
        """Handle reaction added to bot message.

        Args:
            event: Slack event
            client: Slack client
        """
        reaction = event.get("reaction", "")
        item = event.get("item", {})
        user_id = event.get("user", "")

        # Track positive/negative reactions for feedback
        if reaction in ["+1", "thumbsup", "white_check_mark"]:
            logger.info("Positive reaction", user_id=user_id, message_ts=item.get("ts"))
        elif reaction in ["-1", "thumbsdown", "x"]:
            logger.info("Negative reaction", user_id=user_id, message_ts=item.get("ts"))


async def process_mention_query(
    query: str,
    user_id: str,
    team_id: str,
    channel_id: str,
    thread_ts: str,
    say,
    client: AsyncWebClient,
    app: AsyncApp,
) -> None:
    """Process a query from an app mention.

    Args:
        query: Query text
        user_id: Slack user ID
        team_id: Slack team ID
        channel_id: Channel ID
        thread_ts: Thread timestamp
        say: Say function
        client: Slack client
        app: Bolt app
    """
    # Send thinking indicator
    thinking_msg = await say(
        blocks=loading_blocks("Thinking..."),
        thread_ts=thread_ts,
    )

    try:
        user_service = UserService(app._settings.redis_url)
        user = await user_service.get_or_create_user(user_id, team_id)

        if not user.is_linked:
            await client.chat_update(
                channel=channel_id,
                ts=thinking_msg["ts"],
                blocks=error_blocks(
                    "Not connected to ASWA",
                    "An admin needs to run /aswa-config link <tenant-id>"
                ),
            )
            return

        # Execute query
        query_client: QueryClient = app._query_client
        result = await query_client.query(
            tenant_id=user.aswa_tenant_id,
            query=query,
            user_id=user_id,
        )

        # Format response
        blocks = answer_blocks(
            result.get("answer", "I couldn't find an answer."),
            result.get("citations", []),
        )

        blocks.append(context_block([
            f"Confidence: {format_confidence(result.get('confidence', 0))}",
        ]))

        blocks.append(actions_block([
            button_block("Helpful", "feedback_helpful", value=str(result.get("query_id", ""))),
            button_block("Not Helpful", "feedback_not_helpful", value=str(result.get("query_id", ""))),
        ]))

        await client.chat_update(
            channel=channel_id,
            ts=thinking_msg["ts"],
            blocks=blocks,
        )

    except Exception as e:
        logger.error("Mention query failed", error=str(e))
        await client.chat_update(
            channel=channel_id,
            ts=thinking_msg["ts"],
            blocks=error_blocks("Something went wrong", "Please try again later"),
        )


async def process_dm_query(
    query: str,
    user_id: str,
    team_id: str,
    say,
    client: AsyncWebClient,
    app: AsyncApp,
) -> None:
    """Process a query from a DM.

    Args:
        query: Query text
        user_id: Slack user ID
        team_id: Slack team ID
        say: Say function
        client: Slack client
        app: Bolt app
    """
    try:
        user_service = UserService(app._settings.redis_url)
        user = await user_service.get_or_create_user(user_id, team_id)

        if not user.is_linked:
            await say(blocks=error_blocks(
                "Not connected to ASWA",
                "Ask an admin to connect your workspace using /aswa-config"
            ))
            return

        # Send typing indicator
        await say(blocks=loading_blocks())

        # Execute query
        query_client: QueryClient = app._query_client
        result = await query_client.query(
            tenant_id=user.aswa_tenant_id,
            query=query,
            user_id=user_id,
        )

        blocks = answer_blocks(
            result.get("answer", "I couldn't find an answer."),
            result.get("citations", []),
            query=query,
        )

        blocks.append(actions_block([
            button_block("Ask Follow-up", "refine_query", value=query),
        ]))

        await say(blocks=blocks)

    except Exception as e:
        logger.error("DM query failed", error=str(e))
        await say(blocks=error_blocks("Something went wrong"))


async def handle_dm_status(say, app: AsyncApp) -> None:
    """Handle status check in DM.

    Args:
        say: Say function
        app: Bolt app
    """
    try:
        query_client: QueryClient = app._query_client
        is_healthy = await query_client.health_check()

        if is_healthy:
            await say(text="All systems are operational!")
        else:
            await say(text="Some services may be experiencing issues.")

    except Exception:
        await say(text="Unable to check status.")


async def build_home_view(user_id: str, team_id: str, app: AsyncApp) -> dict:
    """Build the app home view.

    Args:
        user_id: Slack user ID
        team_id: Slack team ID
        app: Bolt app

    Returns:
        Home view definition
    """
    user_service = UserService(app._settings.redis_url)
    user = await user_service.get_or_create_user(user_id, team_id)

    blocks = [
        header_block("Welcome to ASWA"),
        text_block("Your AI-powered document intelligence assistant"),
        divider_block(),
    ]

    if user.is_linked:
        blocks.extend([
            text_block("*Connected to ASWA*"),
            context_block([f"Tenant: {user.aswa_tenant_id}"]),
            divider_block(),
            header_block("Quick Actions"),
            actions_block([
                button_block("View Insights", "view_insights", value="all", style="primary"),
                button_block("View Risks", "view_insights", value="risks"),
                button_block("View Digest", "view_digest", value="daily"),
            ]),
            divider_block(),
            text_block("*Recent Activity*"),
            context_block(["Loading recent queries..."]),
        ])
    else:
        blocks.extend([
            text_block("*Not connected*"),
            text_block("Ask an admin to connect your workspace to ASWA."),
            divider_block(),
            text_block("*Getting Started*"),
            text_block(
                "1. An admin runs `/aswa-config link <tenant-id>`\n"
                "2. Mention me in a channel: `@ASWA what are the risks?`\n"
                "3. Or DM me directly with questions"
            ),
        ])

    blocks.extend([
        divider_block(),
        context_block(["ASWA v1.0.0 | /aswa help for more info"]),
    ])

    return {
        "type": "home",
        "blocks": blocks,
    }


def get_dm_help_blocks() -> list[dict]:
    """Get help blocks for DM.

    Returns:
        List of Slack blocks
    """
    return [
        header_block("ASWA Direct Message Help"),
        text_block("You can ask me questions directly here!"),
        divider_block(),
        text_block("*Examples:*"),
        context_block([
            "- What are the main risks in the Q4 report?",
            "- Summarize the financial highlights",
            "- Compare revenue across regions",
        ]),
        divider_block(),
        text_block("*Commands:*"),
        text_block(
            "- `help` - Show this help message\n"
            "- `status` - Check ASWA status"
        ),
        divider_block(),
        context_block(["You can also use /aswa commands in any channel"]),
    ]
