"""Tests for interactive component handlers."""
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

    @pytest.mark.asyncio
    async def test_update_message_handles_error(self):
        """Test that errors are handled gracefully."""
        mock_client = AsyncMock()
        mock_client.chat_update = AsyncMock(side_effect=Exception("API error"))

        body = {
            "channel": {"id": "C123"},
            "message": {
                "ts": "123.456",
                "blocks": [],
            },
        }

        # Should not raise
        await update_message_with_thanks(body, mock_client, "Thanks!")
