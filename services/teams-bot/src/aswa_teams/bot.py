from typing import Any
from uuid import UUID
import structlog

from botbuilder.core import (
    ActivityHandler,
    ConversationState,
    TurnContext,
    UserState,
    MessageFactory,
)
from botbuilder.schema import (
    Activity,
    ActivityTypes,
    ChannelAccount,
    Attachment,
)

from .config import Settings
from .services.query_client import QueryClient
from .services.user_service import UserService
from .cards.adaptive_cards import (
    create_answer_card,
    create_insights_card,
    create_error_card,
    create_welcome_card,
    create_help_card,
)

logger = structlog.get_logger()


class ASWABot(ActivityHandler):
    """ASWA Teams Bot handler."""

    def __init__(
        self,
        settings: Settings,
        conversation_state: ConversationState,
        user_state: UserState,
        query_client: QueryClient,
        user_service: UserService,
    ):
        self.settings = settings
        self.conversation_state = conversation_state
        self.user_state = user_state
        self.query_client = query_client
        self.user_service = user_service

        # State accessors
        self.user_profile_accessor = self.user_state.create_property("UserProfile")
        self.conversation_data_accessor = self.conversation_state.create_property("ConversationData")

    async def on_turn(self, turn_context: TurnContext):
        """Handle each turn."""
        await super().on_turn(turn_context)

        # Save state changes
        await self.conversation_state.save_changes(turn_context)
        await self.user_state.save_changes(turn_context)

    async def on_members_added_activity(
        self,
        members_added: list[ChannelAccount],
        turn_context: TurnContext,
    ):
        """Handle new members added to conversation."""
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                # Send welcome card
                welcome_card = create_welcome_card(self.settings.bot_name)
                await turn_context.send_activity(
                    MessageFactory.attachment(welcome_card)
                )

    async def on_message_activity(self, turn_context: TurnContext):
        """Handle incoming messages."""
        text = turn_context.activity.text.strip() if turn_context.activity.text else ""
        user_id = turn_context.activity.from_property.id
        conversation_id = turn_context.activity.conversation.id

        logger.info(
            "Message received",
            user_id=user_id,
            text=text[:50] if text else "(empty)",
        )

        # Handle empty message
        if not text:
            await turn_context.send_activity("Please enter a question or type 'help' for assistance.")
            return

        # Handle commands
        lower_text = text.lower()

        if lower_text == "help":
            help_card = create_help_card()
            await turn_context.send_activity(MessageFactory.attachment(help_card))
            return

        if lower_text == "status":
            await self._handle_status(turn_context)
            return

        if lower_text.startswith("link "):
            tenant_id = text[5:].strip()
            await self._handle_link(turn_context, user_id, tenant_id)
            return

        if lower_text == "insights":
            await self._handle_insights(turn_context, user_id)
            return

        if lower_text.startswith("insights "):
            insight_type = text[9:].strip()
            await self._handle_insights(turn_context, user_id, insight_type)
            return

        # Handle as query
        await self._handle_query(turn_context, text, user_id)

    async def _handle_query(
        self,
        turn_context: TurnContext,
        query: str,
        user_id: str,
    ) -> None:
        """Handle a user query.

        Args:
            turn_context: Turn context
            query: User query
            user_id: User identifier
        """
        # Send typing indicator
        await turn_context.send_activity(Activity(type=ActivityTypes.typing))

        try:
            # Get user
            user = await self.user_service.get_or_create_user(user_id)

            if not user.is_linked:
                error_card = create_error_card(
                    "Not Connected",
                    "Please link your account first by typing: link <tenant-id>"
                )
                await turn_context.send_activity(MessageFactory.attachment(error_card))
                return

            # Execute query
            result = await self.query_client.query(
                tenant_id=user.aswa_tenant_id,
                query=query,
                user_id=user_id,
            )

            # Create answer card
            answer_card = create_answer_card(
                query=query,
                answer=result.get("answer", "No answer found."),
                citations=result.get("citations", []),
                confidence=result.get("confidence", 0),
                query_id=result.get("query_id", ""),
            )

            await turn_context.send_activity(MessageFactory.attachment(answer_card))

            logger.info(
                "Query answered",
                user_id=user_id,
                query=query[:50],
                confidence=result.get("confidence", 0),
            )

        except Exception as e:
            logger.error("Query failed", error=str(e))
            error_card = create_error_card(
                "Query Failed",
                "Something went wrong. Please try again."
            )
            await turn_context.send_activity(MessageFactory.attachment(error_card))

    async def _handle_status(self, turn_context: TurnContext) -> None:
        """Handle status command."""
        try:
            is_healthy = await self.query_client.health_check()

            if is_healthy:
                await turn_context.send_activity("All systems operational!")
            else:
                await turn_context.send_activity("Some services may be unavailable.")

        except Exception:
            await turn_context.send_activity("Unable to check status.")

    async def _handle_link(
        self,
        turn_context: TurnContext,
        user_id: str,
        tenant_id_str: str,
    ) -> None:
        """Handle link command."""
        try:
            tenant_id = UUID(tenant_id_str)

            await self.user_service.link_user_to_tenant(
                teams_user_id=user_id,
                tenant_id=tenant_id,
            )

            await turn_context.send_activity(
                f"Successfully linked to tenant `{tenant_id}`!\n\n"
                "You can now ask questions about your documents."
            )

        except ValueError:
            await turn_context.send_activity(
                "Invalid tenant ID. Please provide a valid UUID."
            )

    async def _handle_insights(
        self,
        turn_context: TurnContext,
        user_id: str,
        insight_type: str = "all",
    ) -> None:
        """Handle insights command."""
        try:
            user = await self.user_service.get_or_create_user(user_id)

            if not user.is_linked:
                await turn_context.send_activity(
                    "Not connected. Use `link <tenant-id>` first."
                )
                return

            types = [insight_type] if insight_type != "all" else None

            result = await self.query_client.get_insights(
                tenant_id=user.aswa_tenant_id,
                insight_types=types,
                limit=self.settings.max_results_per_message,
            )

            insights = result.get("insights", [])

            if not insights:
                await turn_context.send_activity(f"No {insight_type} insights found.")
                return

            insights_card = create_insights_card(insights, insight_type)
            await turn_context.send_activity(MessageFactory.attachment(insights_card))

        except Exception as e:
            logger.error("Insights fetch failed", error=str(e))
            await turn_context.send_activity("Failed to fetch insights.")

    async def on_invoke_activity(self, turn_context: TurnContext) -> Any:
        """Handle invoke activities (adaptive card actions)."""
        activity = turn_context.activity

        if activity.name == "adaptiveCard/action":
            action = activity.value.get("action", {})
            action_type = action.get("type", "")
            action_data = action.get("data", {})

            if action_type == "feedback":
                return await self._handle_feedback_action(turn_context, action_data)
            elif action_type == "refine":
                return await self._handle_refine_action(turn_context, action_data)

        return None

    async def _handle_feedback_action(
        self,
        turn_context: TurnContext,
        data: dict,
    ) -> dict:
        """Handle feedback card action."""
        query_id = data.get("query_id", "")
        feedback = data.get("feedback", "")
        user_id = turn_context.activity.from_property.id

        logger.info(
            "Feedback received",
            query_id=query_id,
            feedback=feedback,
            user_id=user_id,
        )

        return {
            "statusCode": 200,
            "type": "application/vnd.microsoft.activity.message",
            "value": "Thanks for your feedback!",
        }

    async def _handle_refine_action(
        self,
        turn_context: TurnContext,
        data: dict,
    ) -> dict:
        """Handle refine query action."""
        refined_query = data.get("query", "")
        user_id = turn_context.activity.from_property.id

        if refined_query:
            await self._handle_query(turn_context, refined_query, user_id)

        return {"statusCode": 200}
