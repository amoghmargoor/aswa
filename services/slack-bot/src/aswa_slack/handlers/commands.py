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
    insight_blocks,
    error_blocks,
    loading_blocks,
)
from ..utils.formatting import format_confidence, truncate_text

logger = structlog.get_logger()


def register_commands(app: AsyncApp) -> None:
    """Register slash command handlers.

    Args:
        app: Slack Bolt app
    """

    @app.command("/aswa")
    async def handle_aswa_command(ack, body, say, client: AsyncWebClient):
        """Handle /aswa command for queries.

        Usage:
            /aswa <query>
            /aswa help
            /aswa status
        """
        await ack()

        user_id = body.get("user_id", "")
        team_id = body.get("team_id", "")
        channel_id = body.get("channel_id", "")
        text = body.get("text", "").strip()

        logger.info(
            "ASWA command received",
            user_id=user_id,
            team_id=team_id,
            text=text[:50] if text else "(empty)",
        )

        # Handle empty or help command
        if not text or text.lower() == "help":
            await say(blocks=get_help_blocks())
            return

        # Handle status command
        if text.lower() == "status":
            await handle_status(say, app)
            return

        # Handle query
        await handle_query(
            text=text,
            user_id=user_id,
            team_id=team_id,
            channel_id=channel_id,
            say=say,
            client=client,
            app=app,
        )

    @app.command("/aswa-insights")
    async def handle_insights_command(ack, body, say, client: AsyncWebClient):
        """Handle /aswa-insights command.

        Usage:
            /aswa-insights [type]
            /aswa-insights risks
            /aswa-insights opportunities
        """
        await ack()

        user_id = body.get("user_id", "")
        team_id = body.get("team_id", "")
        text = body.get("text", "").strip().lower()

        logger.info(
            "Insights command received",
            user_id=user_id,
            team_id=team_id,
            filter=text,
        )

        await handle_insights(
            insight_type=text or "all",
            user_id=user_id,
            team_id=team_id,
            say=say,
            app=app,
        )

    @app.command("/aswa-config")
    async def handle_config_command(ack, body, say, client: AsyncWebClient):
        """Handle /aswa-config command.

        Usage:
            /aswa-config
            /aswa-config set <key> <value>
            /aswa-config link <tenant-id>
        """
        await ack()

        user_id = body.get("user_id", "")
        team_id = body.get("team_id", "")
        text = body.get("text", "").strip()

        logger.info(
            "Config command received",
            user_id=user_id,
            team_id=team_id,
            text=text,
        )

        await handle_config(
            text=text,
            user_id=user_id,
            team_id=team_id,
            say=say,
            client=client,
            app=app,
        )

    @app.command("/aswa-digest")
    async def handle_digest_command(ack, body, say, client: AsyncWebClient):
        """Handle /aswa-digest command.

        Usage:
            /aswa-digest [daily|weekly]
        """
        await ack()

        user_id = body.get("user_id", "")
        team_id = body.get("team_id", "")
        text = body.get("text", "").strip().lower()
        period = text if text in ["daily", "weekly"] else "daily"

        logger.info(
            "Digest command received",
            user_id=user_id,
            team_id=team_id,
            period=period,
        )

        await handle_digest(
            period=period,
            user_id=user_id,
            team_id=team_id,
            say=say,
            app=app,
        )

    @app.command("/aswa-search")
    async def handle_search_command(ack, body, say, client: AsyncWebClient):
        """Handle /aswa-search command.

        Usage:
            /aswa-search <query>
        """
        await ack()

        user_id = body.get("user_id", "")
        team_id = body.get("team_id", "")
        text = body.get("text", "").strip()

        if not text:
            await say(blocks=error_blocks(
                "Please provide a search query",
                "Usage: /aswa-search <query>"
            ))
            return

        logger.info(
            "Search command received",
            user_id=user_id,
            team_id=team_id,
            query=text[:50],
        )

        await handle_search(
            query=text,
            user_id=user_id,
            team_id=team_id,
            say=say,
            app=app,
        )


async def handle_query(
    text: str,
    user_id: str,
    team_id: str,
    channel_id: str,
    say,
    client: AsyncWebClient,
    app: AsyncApp,
) -> None:
    """Process a user query.

    Args:
        text: Query text
        user_id: Slack user ID
        team_id: Slack team ID
        channel_id: Channel ID
        say: Say function
        client: Slack client
        app: Bolt app
    """
    # Send loading message
    loading_response = await say(blocks=loading_blocks("Processing your query..."))
    loading_ts = loading_response.get("ts")

    try:
        # Get user and tenant info
        user_service = UserService(app._settings.redis_url)
        user = await user_service.get_or_create_user(user_id, team_id)

        if not user.is_linked:
            await client.chat_update(
                channel=channel_id,
                ts=loading_ts,
                blocks=error_blocks(
                    "Not connected to ASWA",
                    "Use /aswa-config link <tenant-id> to connect your workspace"
                ),
            )
            return

        # Execute query
        query_client: QueryClient = app._query_client
        result = await query_client.query(
            tenant_id=user.aswa_tenant_id,
            query=text,
            user_id=user_id,
        )

        # Format response
        answer = result.get("answer", "No answer available")
        citations = result.get("citations", [])
        confidence = result.get("confidence", 0)

        blocks = answer_blocks(answer, citations, query=text)

        # Add confidence and actions
        blocks.append(context_block([
            f"Confidence: {format_confidence(confidence)}",
            f"Query ID: {result.get('query_id', 'N/A')[:8]}",
        ]))

        blocks.append(actions_block([
            button_block("Helpful", "feedback_helpful", value=str(result.get("query_id", ""))),
            button_block("Not Helpful", "feedback_not_helpful", value=str(result.get("query_id", ""))),
            button_block("Refine", "refine_query", value=text),
        ]))

        # Update message with response
        await client.chat_update(
            channel=channel_id,
            ts=loading_ts,
            blocks=blocks,
        )

        logger.info(
            "Query response sent",
            user_id=user_id,
            query=text[:50],
            confidence=confidence,
        )

    except Exception as e:
        logger.error("Query failed", error=str(e), user_id=user_id)
        await client.chat_update(
            channel=channel_id,
            ts=loading_ts,
            blocks=error_blocks(
                "Failed to process query",
                "Please try again later or contact support"
            ),
        )


async def handle_status(say, app: AsyncApp) -> None:
    """Handle status command.

    Args:
        say: Say function
        app: Bolt app
    """
    try:
        query_client: QueryClient = app._query_client
        is_healthy = await query_client.health_check()

        if is_healthy:
            blocks = [
                header_block("ASWA Status"),
                text_block("All systems operational"),
                context_block([
                    f"Query Service: Online",
                    f"Bot Version: 1.0.0",
                ]),
            ]
        else:
            blocks = [
                header_block("ASWA Status"),
                text_block("Some services may be unavailable"),
                context_block(["Query Service: Offline"]),
            ]

        await say(blocks=blocks)

    except Exception as e:
        logger.error("Status check failed", error=str(e))
        await say(blocks=error_blocks("Failed to check status"))


async def handle_insights(
    insight_type: str,
    user_id: str,
    team_id: str,
    say,
    app: AsyncApp,
) -> None:
    """Handle insights command.

    Args:
        insight_type: Type filter
        user_id: Slack user ID
        team_id: Slack team ID
        say: Say function
        app: Bolt app
    """
    try:
        user_service = UserService(app._settings.redis_url)
        user = await user_service.get_or_create_user(user_id, team_id)

        if not user.is_linked:
            await say(blocks=error_blocks(
                "Not connected to ASWA",
                "Use /aswa-config link <tenant-id> to connect"
            ))
            return

        # Get insights
        query_client: QueryClient = app._query_client

        types = None
        if insight_type == "risks":
            types = ["risk"]
        elif insight_type == "opportunities":
            types = ["opportunity"]
        elif insight_type != "all":
            types = [insight_type]

        result = await query_client.get_insights(
            tenant_id=user.aswa_tenant_id,
            insight_types=types,
            limit=app._settings.max_results_per_message,
        )

        insights = result.get("insights", [])

        if not insights:
            await say(blocks=[
                header_block("Insights"),
                text_block(f"No {insight_type} insights found"),
            ])
            return

        blocks = insight_blocks(insights, insight_type)

        # Add navigation
        blocks.append(actions_block([
            button_block("View All Risks", "view_insights", value="risks"),
            button_block("View All Opportunities", "view_insights", value="opportunities"),
        ]))

        await say(blocks=blocks)

    except Exception as e:
        logger.error("Insights fetch failed", error=str(e))
        await say(blocks=error_blocks("Failed to fetch insights"))


async def handle_config(
    text: str,
    user_id: str,
    team_id: str,
    say,
    client: AsyncWebClient,
    app: AsyncApp,
) -> None:
    """Handle config command.

    Args:
        text: Command text
        user_id: Slack user ID
        team_id: Slack team ID
        say: Say function
        client: Slack client
        app: Bolt app
    """
    user_service = UserService(app._settings.redis_url)
    user = await user_service.get_or_create_user(user_id, team_id)

    parts = text.split() if text else []

    if not parts:
        # Show current config
        blocks = [
            header_block("ASWA Configuration"),
            divider_block(),
        ]

        if user.is_linked:
            blocks.append(text_block(f"Connected to tenant: `{user.aswa_tenant_id}`"))
        else:
            blocks.append(text_block("Not connected to ASWA"))
            blocks.append(context_block([
                "Use `/aswa-config link <tenant-id>` to connect"
            ]))

        blocks.append(divider_block())
        blocks.append(text_block("*Preferences:*"))
        blocks.append(text_block(f"- Max results: {app._settings.max_results_per_message}"))

        await say(blocks=blocks)
        return

    action = parts[0].lower()

    if action == "link" and len(parts) >= 2:
        # Link to tenant
        try:
            tenant_id = UUID(parts[1])
            await user_service.link_user_to_tenant(
                slack_user_id=user_id,
                slack_team_id=team_id,
                tenant_id=tenant_id,
            )
            await say(blocks=[
                header_block("Connected!"),
                text_block(f"Successfully linked to tenant `{tenant_id}`"),
                context_block(["You can now use /aswa to query your documents"]),
            ])

        except ValueError:
            await say(blocks=error_blocks(
                "Invalid tenant ID",
                "Please provide a valid UUID"
            ))

    elif action == "unlink":
        # Unlink tenant
        user.aswa_tenant_id = None
        user.aswa_user_id = None
        await user_service.save_user(user)
        await say(blocks=[
            header_block("Disconnected"),
            text_block("Successfully unlinked from ASWA"),
        ])

    else:
        await say(blocks=error_blocks(
            "Unknown config command",
            "Available: link <tenant-id>, unlink"
        ))


async def handle_digest(
    period: str,
    user_id: str,
    team_id: str,
    say,
    app: AsyncApp,
) -> None:
    """Handle digest command.

    Args:
        period: Digest period
        user_id: Slack user ID
        team_id: Slack team ID
        say: Say function
        app: Bolt app
    """
    try:
        user_service = UserService(app._settings.redis_url)
        user = await user_service.get_or_create_user(user_id, team_id)

        if not user.is_linked:
            await say(blocks=error_blocks(
                "Not connected to ASWA",
                "Use /aswa-config link <tenant-id> to connect"
            ))
            return

        query_client: QueryClient = app._query_client
        result = await query_client.get_digest(
            tenant_id=user.aswa_tenant_id,
            period=period,
        )

        blocks = [
            header_block(f"{period.title()} Digest"),
            text_block(result.get("summary", "No summary available")),
            divider_block(),
        ]

        # Add sections
        for section in result.get("sections", []):
            section_name = section.get("name", "")
            items = section.get("items", [])

            if items:
                blocks.append(text_block(f"*{section_name}*"))
                for item in items[:3]:
                    blocks.append(context_block([
                        f"- {item.get('title', '')}: {truncate_text(item.get('description', ''), 100)}"
                    ]))
                blocks.append(divider_block())

        await say(blocks=blocks)

    except Exception as e:
        logger.error("Digest fetch failed", error=str(e))
        await say(blocks=error_blocks("Failed to fetch digest"))


async def handle_search(
    query: str,
    user_id: str,
    team_id: str,
    say,
    app: AsyncApp,
) -> None:
    """Handle search command.

    Args:
        query: Search query
        user_id: Slack user ID
        team_id: Slack team ID
        say: Say function
        app: Bolt app
    """
    try:
        user_service = UserService(app._settings.redis_url)
        user = await user_service.get_or_create_user(user_id, team_id)

        if not user.is_linked:
            await say(blocks=error_blocks(
                "Not connected to ASWA",
                "Use /aswa-config link <tenant-id> to connect"
            ))
            return

        query_client: QueryClient = app._query_client
        result = await query_client.search(
            tenant_id=user.aswa_tenant_id,
            query=query,
            limit=app._settings.max_results_per_message,
        )

        results = result.get("results", [])

        if not results:
            await say(blocks=[
                header_block("Search Results"),
                text_block(f"No results found for: _{query}_"),
            ])
            return

        blocks = [
            header_block("Search Results"),
            context_block([f"Found {len(results)} results for: _{query}_"]),
            divider_block(),
        ]

        for i, item in enumerate(results, 1):
            doc_name = item.get("document_name", "Unknown")
            snippet = truncate_text(item.get("content", ""), 150)
            score = item.get("score", 0)

            blocks.append(text_block(f"*{i}. {doc_name}*"))
            blocks.append(context_block([snippet]))
            blocks.append(context_block([f"Relevance: {score:.0%}"]))
            blocks.append(divider_block())

        await say(blocks=blocks)

    except Exception as e:
        logger.error("Search failed", error=str(e))
        await say(blocks=error_blocks("Search failed"))


def get_help_blocks() -> list[dict]:
    """Get help message blocks.

    Returns:
        List of Slack blocks
    """
    return [
        header_block("ASWA Help"),
        text_block("ASWA helps you analyze and query your business documents."),
        divider_block(),
        text_block("*Available Commands:*"),
        text_block(
            "- `/aswa <question>` - Ask a question about your documents\n"
            "- `/aswa status` - Check ASWA status\n"
            "- `/aswa help` - Show this help message"
        ),
        divider_block(),
        text_block("*More Commands:*"),
        text_block(
            "- `/aswa-insights [type]` - View recent insights\n"
            "- `/aswa-search <query>` - Search documents\n"
            "- `/aswa-digest [daily|weekly]` - View digest\n"
            "- `/aswa-config` - View/update configuration"
        ),
        divider_block(),
        text_block("*Examples:*"),
        context_block([
            "`/aswa What are the main risks in the Q4 report?`",
            "`/aswa-insights risks`",
            "`/aswa-search revenue forecast`",
        ]),
    ]
