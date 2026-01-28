# Task 5.1.4: Slack Bot - Event Handlers

## Context

You are working on the ASWA Slack bot at `/services/slack-bot/`. Interactive components are complete (Task 5.1.3). Now we need to implement event handlers for app mentions, messages, and other Slack events.

## Objective

Create event handlers that:
1. Handle app mentions for conversational queries
2. Process direct messages
3. Handle channel join/leave events
4. Manage home tab updates
5. Support file sharing events

## Requirements

### 1. Create `/services/slack-bot/src/aswa_slack/handlers/events.py`
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
                    text="👋 Hi! I'm ASWA, your AI document assistant. "
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
            button_block("👍", "feedback_helpful", value=str(result.get("query_id", ""))),
            button_block("👎", "feedback_not_helpful", value=str(result.get("query_id", ""))),
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
            button_block("🔄 Ask Follow-up", "refine_query", value=query),
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
            await say(text="✅ All systems are operational!")
        else:
            await say(text="⚠️ Some services may be experiencing issues.")

    except Exception:
        await say(text="❌ Unable to check status.")


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
        header_block("🏠 Welcome to ASWA"),
        text_block("Your AI-powered document intelligence assistant"),
        divider_block(),
    ]

    if user.is_linked:
        blocks.extend([
            text_block("✅ *Connected to ASWA*"),
            context_block([f"Tenant: {user.aswa_tenant_id}"]),
            divider_block(),
            header_block("📊 Quick Actions"),
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
            text_block("❌ *Not connected*"),
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
        header_block("💬 ASWA Direct Message Help"),
        text_block("You can ask me questions directly here!"),
        divider_block(),
        text_block("*Examples:*"),
        context_block([
            "• What are the main risks in the Q4 report?",
            "• Summarize the financial highlights",
            "• Compare revenue across regions",
        ]),
        divider_block(),
        text_block("*Commands:*"),
        text_block(
            "• `help` - Show this help message\n"
            "• `status` - Check ASWA status"
        ),
        divider_block(),
        context_block(["You can also use /aswa commands in any channel"]),
    ]
```

## Test Requirements

### Create `/services/slack-bot/tests/handlers/test_events.py`
```python
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from aswa_slack.handlers.events import (
    process_mention_query,
    process_dm_query,
    build_home_view,
    get_dm_help_blocks,
)


class TestAppMention:
    @pytest.mark.asyncio
    async def test_process_mention_query_not_linked(
        self,
        mock_say,
        settings,
        mock_query_client,
    ):
        """Test mention when user not linked."""
        mock_app = MagicMock()
        mock_app._settings = settings
        mock_app._query_client = mock_query_client

        mock_client = AsyncMock()
        mock_client.chat_update = AsyncMock()

        mock_say.return_value = {"ts": "123.456"}

        with patch("aswa_slack.handlers.events.UserService") as MockUserService:
            mock_user_service = MagicMock()
            mock_user_service.get_or_create_user = AsyncMock(return_value=MagicMock(
                is_linked=False,
            ))
            MockUserService.return_value = mock_user_service

            await process_mention_query(
                query="What are the risks?",
                user_id="U123",
                team_id="T123",
                channel_id="C123",
                thread_ts="123.456",
                say=mock_say,
                client=mock_client,
                app=mock_app,
            )

            # Should update with error
            mock_client.chat_update.assert_called()

    @pytest.mark.asyncio
    async def test_process_mention_query_success(
        self,
        mock_say,
        settings,
        mock_query_client,
    ):
        """Test successful mention query."""
        mock_app = MagicMock()
        mock_app._settings = settings
        mock_app._query_client = mock_query_client

        mock_client = AsyncMock()
        mock_client.chat_update = AsyncMock()

        mock_say.return_value = {"ts": "123.456"}

        tenant_id = uuid4()

        with patch("aswa_slack.handlers.events.UserService") as MockUserService:
            mock_user_service = MagicMock()
            mock_user_service.get_or_create_user = AsyncMock(return_value=MagicMock(
                is_linked=True,
                aswa_tenant_id=tenant_id,
            ))
            MockUserService.return_value = mock_user_service

            await process_mention_query(
                query="What are the risks?",
                user_id="U123",
                team_id="T123",
                channel_id="C123",
                thread_ts="123.456",
                say=mock_say,
                client=mock_client,
                app=mock_app,
            )

            mock_query_client.query.assert_called_once()
            mock_client.chat_update.assert_called()


class TestDirectMessage:
    @pytest.mark.asyncio
    async def test_process_dm_query_not_linked(
        self,
        mock_say,
        settings,
        mock_query_client,
    ):
        """Test DM when user not linked."""
        mock_app = MagicMock()
        mock_app._settings = settings
        mock_app._query_client = mock_query_client

        mock_client = AsyncMock()

        with patch("aswa_slack.handlers.events.UserService") as MockUserService:
            mock_user_service = MagicMock()
            mock_user_service.get_or_create_user = AsyncMock(return_value=MagicMock(
                is_linked=False,
            ))
            MockUserService.return_value = mock_user_service

            await process_dm_query(
                query="What are the risks?",
                user_id="U123",
                team_id="T123",
                say=mock_say,
                client=mock_client,
                app=mock_app,
            )

            # Should show error
            assert mock_say.call_count >= 1


class TestHomeView:
    @pytest.mark.asyncio
    async def test_build_home_view_linked(self, settings):
        """Test home view for linked user."""
        mock_app = MagicMock()
        mock_app._settings = settings

        tenant_id = uuid4()

        with patch("aswa_slack.handlers.events.UserService") as MockUserService:
            mock_user_service = MagicMock()
            mock_user_service.get_or_create_user = AsyncMock(return_value=MagicMock(
                is_linked=True,
                aswa_tenant_id=tenant_id,
            ))
            MockUserService.return_value = mock_user_service

            view = await build_home_view("U123", "T123", mock_app)

            assert view["type"] == "home"
            assert "blocks" in view
            assert any("connected" in str(b).lower() for b in view["blocks"])

    @pytest.mark.asyncio
    async def test_build_home_view_not_linked(self, settings):
        """Test home view for unlinked user."""
        mock_app = MagicMock()
        mock_app._settings = settings

        with patch("aswa_slack.handlers.events.UserService") as MockUserService:
            mock_user_service = MagicMock()
            mock_user_service.get_or_create_user = AsyncMock(return_value=MagicMock(
                is_linked=False,
            ))
            MockUserService.return_value = mock_user_service

            view = await build_home_view("U123", "T123", mock_app)

            assert view["type"] == "home"
            assert any("not connected" in str(b).lower() for b in view["blocks"])


class TestHelpBlocks:
    def test_get_dm_help_blocks(self):
        """Test DM help blocks."""
        blocks = get_dm_help_blocks()

        assert len(blocks) > 0
        assert any("help" in str(b).lower() for b in blocks)
        assert any("examples" in str(b).lower() for b in blocks)
```

## Verification

1. Run tests: `cd /services/slack-bot && python -m pytest tests/handlers/test_events.py -v`
2. Verify imports: `python -c "from aswa_slack.handlers.events import register_events"`
3. Test app mentions and DMs in Slack workspace
