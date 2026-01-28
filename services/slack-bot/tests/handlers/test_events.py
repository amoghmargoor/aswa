"""Tests for event handlers."""
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
