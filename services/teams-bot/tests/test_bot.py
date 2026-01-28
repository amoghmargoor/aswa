import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from aswa_teams.bot import ASWABot
from aswa_teams.services.user_service import TeamsUser


class TestASWABot:
    @pytest.fixture
    def bot(self, settings, mock_query_client, mock_user_service):
        conversation_state = MagicMock()
        conversation_state.create_property = MagicMock(return_value=MagicMock())
        conversation_state.save_changes = AsyncMock()
        user_state = MagicMock()
        user_state.create_property = MagicMock(return_value=MagicMock())
        user_state.save_changes = AsyncMock()

        return ASWABot(
            settings=settings,
            conversation_state=conversation_state,
            user_state=user_state,
            query_client=mock_query_client,
            user_service=mock_user_service,
        )

    @pytest.fixture
    def turn_context(self):
        context = MagicMock()
        context.activity.text = "What are the risks?"
        context.activity.from_property.id = "user-123"
        context.activity.conversation.id = "conv-123"
        context.activity.recipient.id = "bot-123"
        context.send_activity = AsyncMock()
        return context

    @pytest.mark.asyncio
    async def test_handle_help_command(self, bot, turn_context):
        """Test help command."""
        turn_context.activity.text = "help"

        await bot.on_message_activity(turn_context)

        turn_context.send_activity.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_status_command(self, bot, turn_context):
        """Test status command."""
        turn_context.activity.text = "status"

        await bot.on_message_activity(turn_context)

        turn_context.send_activity.assert_called()

    @pytest.mark.asyncio
    async def test_handle_status_healthy(self, bot, turn_context, mock_query_client):
        """Test status when healthy."""
        turn_context.activity.text = "status"
        mock_query_client.health_check.return_value = True

        await bot.on_message_activity(turn_context)

        call_args = turn_context.send_activity.call_args
        assert "operational" in str(call_args).lower()

    @pytest.mark.asyncio
    async def test_handle_status_unhealthy(self, bot, turn_context, mock_query_client):
        """Test status when unhealthy."""
        turn_context.activity.text = "status"
        mock_query_client.health_check.return_value = False

        await bot.on_message_activity(turn_context)

        call_args = turn_context.send_activity.call_args
        assert "unavailable" in str(call_args).lower()

    @pytest.mark.asyncio
    async def test_handle_query_not_linked(
        self,
        bot,
        turn_context,
        mock_user_service,
    ):
        """Test query when user not linked."""
        mock_user_service.get_or_create_user.return_value = TeamsUser(
            teams_user_id="user-123",
            aswa_tenant_id=None,
        )

        await bot.on_message_activity(turn_context)

        # Should send error about not being connected
        turn_context.send_activity.assert_called()

    @pytest.mark.asyncio
    async def test_handle_query_success(
        self,
        bot,
        turn_context,
        mock_user_service,
        mock_query_client,
    ):
        """Test successful query."""
        tenant_id = uuid4()
        mock_user_service.get_or_create_user.return_value = TeamsUser(
            teams_user_id="user-123",
            aswa_tenant_id=tenant_id,
        )

        await bot.on_message_activity(turn_context)

        mock_query_client.query.assert_called_once()
        turn_context.send_activity.assert_called()

    @pytest.mark.asyncio
    async def test_handle_empty_message(self, bot, turn_context):
        """Test empty message handling."""
        turn_context.activity.text = ""

        await bot.on_message_activity(turn_context)

        turn_context.send_activity.assert_called()
        call_args = str(turn_context.send_activity.call_args)
        assert "help" in call_args.lower() or "question" in call_args.lower()

    @pytest.mark.asyncio
    async def test_handle_link_command(
        self,
        bot,
        turn_context,
        mock_user_service,
    ):
        """Test link command."""
        tenant_id = uuid4()
        turn_context.activity.text = f"link {tenant_id}"

        await bot.on_message_activity(turn_context)

        mock_user_service.link_user_to_tenant.assert_called_once()
        call_args = str(turn_context.send_activity.call_args)
        assert "linked" in call_args.lower() or "successfully" in call_args.lower()

    @pytest.mark.asyncio
    async def test_handle_link_invalid_uuid(
        self,
        bot,
        turn_context,
    ):
        """Test link with invalid UUID."""
        turn_context.activity.text = "link not-a-uuid"

        await bot.on_message_activity(turn_context)

        call_args = str(turn_context.send_activity.call_args)
        assert "invalid" in call_args.lower()

    @pytest.mark.asyncio
    async def test_handle_insights_not_linked(
        self,
        bot,
        turn_context,
        mock_user_service,
    ):
        """Test insights when not linked."""
        turn_context.activity.text = "insights"
        mock_user_service.get_or_create_user.return_value = TeamsUser(
            teams_user_id="user-123",
            aswa_tenant_id=None,
        )

        await bot.on_message_activity(turn_context)

        call_args = str(turn_context.send_activity.call_args)
        assert "not connected" in call_args.lower() or "link" in call_args.lower()

    @pytest.mark.asyncio
    async def test_handle_insights_success(
        self,
        bot,
        turn_context,
        mock_user_service,
        mock_query_client,
    ):
        """Test successful insights retrieval."""
        tenant_id = uuid4()
        mock_user_service.get_or_create_user.return_value = TeamsUser(
            teams_user_id="user-123",
            aswa_tenant_id=tenant_id,
        )
        mock_query_client.get_insights.return_value = {
            "insights": [
                {"title": "Test", "description": "Test insight", "confidence": 0.8}
            ]
        }

        turn_context.activity.text = "insights"

        await bot.on_message_activity(turn_context)

        mock_query_client.get_insights.assert_called_once()

    @pytest.mark.asyncio
    async def test_welcome_new_member(self, bot, turn_context):
        """Test welcome message for new members."""
        member = MagicMock()
        member.id = "new-user-123"

        await bot.on_members_added_activity([member], turn_context)

        turn_context.send_activity.assert_called_once()
