"""Tests for slash command handlers."""
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from aswa_slack.handlers.commands import (
    handle_query,
    handle_status,
    handle_insights,
    handle_config,
    get_help_blocks,
)


class TestHelpBlocks:
    def test_get_help_blocks(self):
        """Test help blocks generation."""
        blocks = get_help_blocks()

        assert len(blocks) > 0
        assert any("help" in str(block).lower() for block in blocks)

    def test_help_blocks_contains_commands(self):
        """Test help blocks contain command info."""
        blocks = get_help_blocks()

        # Find the section with commands
        text_content = str(blocks)

        assert "/aswa" in text_content
        assert "/aswa-insights" in text_content
        assert "/aswa-search" in text_content


class TestQueryHandler:
    @pytest.mark.asyncio
    async def test_handle_query_not_linked(
        self,
        mock_say,
        mock_query_client,
        settings,
    ):
        """Test query handler when user not linked."""
        mock_app = MagicMock()
        mock_app._settings = settings
        mock_app._query_client = mock_query_client

        mock_client = AsyncMock()
        mock_client.chat_update = AsyncMock()

        mock_say.return_value = {"ts": "123.456"}

        with patch("aswa_slack.handlers.commands.UserService") as MockUserService:
            mock_user_service = MagicMock()
            mock_user_service.get_or_create_user = AsyncMock(return_value=MagicMock(
                is_linked=False,
                aswa_tenant_id=None,
            ))
            MockUserService.return_value = mock_user_service

            await handle_query(
                text="What are the risks?",
                user_id="U123",
                team_id="T123",
                channel_id="C123",
                say=mock_say,
                client=mock_client,
                app=mock_app,
            )

            # Should update message with error
            mock_client.chat_update.assert_called_once()
            call_kwargs = mock_client.chat_update.call_args.kwargs
            assert "blocks" in call_kwargs

    @pytest.mark.asyncio
    async def test_handle_query_success(
        self,
        mock_say,
        mock_query_client,
        settings,
    ):
        """Test successful query handling."""
        mock_app = MagicMock()
        mock_app._settings = settings
        mock_app._query_client = mock_query_client

        mock_client = AsyncMock()
        mock_client.chat_update = AsyncMock()

        mock_say.return_value = {"ts": "123.456"}

        tenant_id = uuid4()

        with patch("aswa_slack.handlers.commands.UserService") as MockUserService:
            mock_user_service = MagicMock()
            mock_user_service.get_or_create_user = AsyncMock(return_value=MagicMock(
                is_linked=True,
                aswa_tenant_id=tenant_id,
            ))
            MockUserService.return_value = mock_user_service

            await handle_query(
                text="What are the risks?",
                user_id="U123",
                team_id="T123",
                channel_id="C123",
                say=mock_say,
                client=mock_client,
                app=mock_app,
            )

            # Should call query client
            mock_query_client.query.assert_called_once()

            # Should update message with response
            mock_client.chat_update.assert_called()


class TestStatusHandler:
    @pytest.mark.asyncio
    async def test_handle_status_healthy(self, mock_say, mock_query_client):
        """Test status when service is healthy."""
        mock_app = MagicMock()
        mock_app._query_client = mock_query_client
        mock_query_client.health_check = AsyncMock(return_value=True)

        await handle_status(mock_say, mock_app)

        mock_say.assert_called_once()
        blocks = mock_say.call_args.kwargs["blocks"]
        assert any("operational" in str(block).lower() for block in blocks)

    @pytest.mark.asyncio
    async def test_handle_status_unhealthy(self, mock_say, mock_query_client):
        """Test status when service is unhealthy."""
        mock_app = MagicMock()
        mock_app._query_client = mock_query_client
        mock_query_client.health_check = AsyncMock(return_value=False)

        await handle_status(mock_say, mock_app)

        mock_say.assert_called_once()
        blocks = mock_say.call_args.kwargs["blocks"]
        assert any("unavailable" in str(block).lower() for block in blocks)


class TestInsightsHandler:
    @pytest.mark.asyncio
    async def test_handle_insights_not_linked(self, mock_say, mock_query_client, settings):
        """Test insights handler when user not linked."""
        mock_app = MagicMock()
        mock_app._settings = settings
        mock_app._query_client = mock_query_client

        with patch("aswa_slack.handlers.commands.UserService") as MockUserService:
            mock_user_service = MagicMock()
            mock_user_service.get_or_create_user = AsyncMock(return_value=MagicMock(
                is_linked=False,
            ))
            MockUserService.return_value = mock_user_service

            await handle_insights(
                insight_type="all",
                user_id="U123",
                team_id="T123",
                say=mock_say,
                app=mock_app,
            )

            mock_say.assert_called_once()
            blocks = mock_say.call_args.kwargs["blocks"]
            assert any("not connected" in str(block).lower() for block in blocks)

    @pytest.mark.asyncio
    async def test_handle_insights_success(self, mock_say, mock_query_client, settings):
        """Test successful insights retrieval."""
        mock_app = MagicMock()
        mock_app._settings = settings
        mock_app._query_client = mock_query_client
        mock_query_client.get_insights = AsyncMock(return_value={
            "insights": [
                {"title": "Test Insight", "description": "Test", "type": "risk", "confidence": 0.9}
            ]
        })

        tenant_id = uuid4()

        with patch("aswa_slack.handlers.commands.UserService") as MockUserService:
            mock_user_service = MagicMock()
            mock_user_service.get_or_create_user = AsyncMock(return_value=MagicMock(
                is_linked=True,
                aswa_tenant_id=tenant_id,
            ))
            MockUserService.return_value = mock_user_service

            await handle_insights(
                insight_type="risks",
                user_id="U123",
                team_id="T123",
                say=mock_say,
                app=mock_app,
            )

            mock_query_client.get_insights.assert_called_once()


class TestConfigHandler:
    @pytest.mark.asyncio
    async def test_handle_config_show(self, mock_say, settings):
        """Test showing current config."""
        mock_app = MagicMock()
        mock_app._settings = settings
        mock_client = AsyncMock()

        with patch("aswa_slack.handlers.commands.UserService") as MockUserService:
            mock_user_service = MagicMock()
            mock_user_service.get_or_create_user = AsyncMock(return_value=MagicMock(
                is_linked=False,
                aswa_tenant_id=None,
            ))
            MockUserService.return_value = mock_user_service

            await handle_config(
                text="",
                user_id="U123",
                team_id="T123",
                say=mock_say,
                client=mock_client,
                app=mock_app,
            )

            mock_say.assert_called_once()
            blocks = mock_say.call_args.kwargs["blocks"]
            assert any("configuration" in str(block).lower() for block in blocks)

    @pytest.mark.asyncio
    async def test_handle_config_link(self, mock_say, settings):
        """Test linking to tenant."""
        mock_app = MagicMock()
        mock_app._settings = settings
        mock_client = AsyncMock()
        tenant_id = uuid4()

        with patch("aswa_slack.handlers.commands.UserService") as MockUserService:
            mock_user_service = MagicMock()
            mock_user_service.get_or_create_user = AsyncMock(return_value=MagicMock(
                is_linked=False,
            ))
            mock_user_service.link_user_to_tenant = AsyncMock()
            MockUserService.return_value = mock_user_service

            await handle_config(
                text=f"link {tenant_id}",
                user_id="U123",
                team_id="T123",
                say=mock_say,
                client=mock_client,
                app=mock_app,
            )

            mock_user_service.link_user_to_tenant.assert_called_once()
            blocks = mock_say.call_args.kwargs["blocks"]
            assert any("connected" in str(block).lower() for block in blocks)

    @pytest.mark.asyncio
    async def test_handle_config_invalid_tenant(self, mock_say, settings):
        """Test linking with invalid tenant ID."""
        mock_app = MagicMock()
        mock_app._settings = settings
        mock_client = AsyncMock()

        with patch("aswa_slack.handlers.commands.UserService") as MockUserService:
            mock_user_service = MagicMock()
            mock_user_service.get_or_create_user = AsyncMock(return_value=MagicMock(
                is_linked=False,
            ))
            MockUserService.return_value = mock_user_service

            await handle_config(
                text="link not-a-uuid",
                user_id="U123",
                team_id="T123",
                say=mock_say,
                client=mock_client,
                app=mock_app,
            )

            blocks = mock_say.call_args.kwargs["blocks"]
            assert any("invalid" in str(block).lower() for block in blocks)
