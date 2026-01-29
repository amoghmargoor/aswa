"""Tests for session manager."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from aswa_agents.generation.session_manager import SessionManager
from aswa_agents.generation.models import (
    AgentCreationSession,
    IntentExtractionResult,
    ExtractedIntent,
    IntentType,
)


@pytest.fixture
def mock_redis():
    """Create mock Redis client."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.delete = AsyncMock()
    return redis


class TestSessionManager:
    """Test SessionManager class."""

    @pytest.mark.asyncio
    async def test_create_session(self, mock_redis):
        """Test creating a new session."""
        with patch.object(SessionManager, '__init__', lambda x, y: None):
            manager = SessionManager(mock_redis)
            manager.redis = mock_redis
            manager.settings = MagicMock()
            manager.settings.redis_prefix = "test:"
            manager.intent_extractor = MagicMock()
            manager._logger = MagicMock()

            session = await manager.create_session("tenant-1", "user-1")

            assert session.tenant_id == "tenant-1"
            assert session.user_id == "user-1"
            assert session.status == "in_progress"
            mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_session(self, mock_redis):
        """Test getting existing session."""
        session = AgentCreationSession(
            tenant_id="tenant-1",
            user_id="user-1",
        )
        mock_redis.get.return_value = session.model_dump_json()

        with patch.object(SessionManager, '__init__', lambda x, y: None):
            manager = SessionManager(mock_redis)
            manager.redis = mock_redis
            manager.settings = MagicMock()
            manager.settings.redis_prefix = "test:"

            result = await manager.get_session(session.id)

            assert result is not None
            assert result.tenant_id == "tenant-1"

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, mock_redis):
        """Test getting non-existent session."""
        mock_redis.get.return_value = None

        with patch.object(SessionManager, '__init__', lambda x, y: None):
            manager = SessionManager(mock_redis)
            manager.redis = mock_redis
            manager.settings = MagicMock()
            manager.settings.redis_prefix = "test:"

            result = await manager.get_session(uuid4())

            assert result is None

    def test_merge_intents(self, mock_redis):
        """Test intent merging logic."""
        with patch.object(SessionManager, '__init__', lambda x, y: None):
            manager = SessionManager(mock_redis)

            previous = IntentExtractionResult(
                original_input="test1",
                normalized_input="test1",
                trigger_intents=[
                    ExtractedIntent(
                        type=IntentType.TRIGGER_ON_EMAIL,
                        confidence=0.7,
                        description="Old trigger",
                    )
                ],
            )

            new = IntentExtractionResult(
                original_input="test2",
                normalized_input="test2",
                trigger_intents=[
                    ExtractedIntent(
                        type=IntentType.TRIGGER_ON_EMAIL,
                        confidence=0.9,
                        description="New trigger",
                    )
                ],
            )

            merged = manager._merge_intents(previous, new)

            assert merged.trigger_intents[0].confidence == 0.9
            assert merged.trigger_intents[0].description == "New trigger"

    def test_merge_intents_adds_new_types(self, mock_redis):
        """Test that merge adds new intent types."""
        with patch.object(SessionManager, '__init__', lambda x, y: None):
            manager = SessionManager(mock_redis)

            previous = IntentExtractionResult(
                original_input="test1",
                normalized_input="test1",
                trigger_intents=[
                    ExtractedIntent(
                        type=IntentType.TRIGGER_ON_EMAIL,
                        confidence=0.9,
                        description="Email trigger",
                    )
                ],
            )

            new = IntentExtractionResult(
                original_input="test2",
                normalized_input="test2",
                action_intents=[
                    ExtractedIntent(
                        type=IntentType.ACTION_SUMMARIZE,
                        confidence=0.8,
                        description="Summarize action",
                    )
                ],
            )

            merged = manager._merge_intents(previous, new)

            assert len(merged.trigger_intents) == 1
            assert len(merged.action_intents) == 1

    def test_merge_intents_none_previous(self, mock_redis):
        """Test merge with no previous intents returns new."""
        with patch.object(SessionManager, '__init__', lambda x, y: None):
            manager = SessionManager(mock_redis)

            new = IntentExtractionResult(
                original_input="test",
                normalized_input="test",
                trigger_intents=[
                    ExtractedIntent(
                        type=IntentType.TRIGGER_ON_EMAIL,
                        confidence=0.9,
                        description="Email trigger",
                    )
                ],
            )

            merged = manager._merge_intents(None, new)

            assert merged == new

    def test_generate_summary(self, mock_redis):
        """Test summary generation."""
        with patch.object(SessionManager, '__init__', lambda x, y: None):
            manager = SessionManager(mock_redis)

            intents = IntentExtractionResult(
                original_input="test",
                normalized_input="test",
                trigger_intents=[
                    ExtractedIntent(
                        type=IntentType.TRIGGER_ON_EMAIL,
                        confidence=0.9,
                        description="Trigger on email received",
                    )
                ],
                action_intents=[
                    ExtractedIntent(
                        type=IntentType.ACTION_SUMMARIZE,
                        confidence=0.85,
                        description="Summarize the content",
                    )
                ],
                overall_confidence=0.87,
            )

            summary = manager._generate_summary(intents)

            assert "Trigger on email received" in summary
            assert "Summarize the content" in summary
            assert "87%" in summary

    @pytest.mark.asyncio
    async def test_complete_session(self, mock_redis):
        """Test completing a session."""
        session = AgentCreationSession(
            tenant_id="tenant-1",
            user_id="user-1",
        )
        mock_redis.get.return_value = session.model_dump_json()

        with patch.object(SessionManager, '__init__', lambda x, y: None):
            manager = SessionManager(mock_redis)
            manager.redis = mock_redis
            manager.settings = MagicMock()
            manager.settings.redis_prefix = "test:"
            manager._logger = MagicMock()

            result = await manager.complete_session(session.id)

            assert result.status == "completed"
            mock_redis.set.assert_called()

    @pytest.mark.asyncio
    async def test_complete_session_not_found(self, mock_redis):
        """Test completing non-existent session raises error."""
        mock_redis.get.return_value = None

        with patch.object(SessionManager, '__init__', lambda x, y: None):
            manager = SessionManager(mock_redis)
            manager.redis = mock_redis
            manager.settings = MagicMock()
            manager.settings.redis_prefix = "test:"

            with pytest.raises(ValueError, match="not found"):
                await manager.complete_session(uuid4())

    @pytest.mark.asyncio
    async def test_cancel_session(self, mock_redis):
        """Test canceling a session."""
        session_id = uuid4()

        with patch.object(SessionManager, '__init__', lambda x, y: None):
            manager = SessionManager(mock_redis)
            manager.redis = mock_redis
            manager.settings = MagicMock()
            manager.settings.redis_prefix = "test:"

            await manager.cancel_session(session_id)

            mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_response_no_intents(self, mock_redis):
        """Test response when no intents accumulated."""
        with patch.object(SessionManager, '__init__', lambda x, y: None):
            manager = SessionManager(mock_redis)
            manager.intent_extractor = MagicMock()

            session = AgentCreationSession(
                tenant_id="tenant-1",
                user_id="user-1",
                accumulated_intents=None,
            )

            response = await manager._generate_response(session)

            assert "help you create an agent" in response

    @pytest.mark.asyncio
    async def test_generate_response_needs_clarification(self, mock_redis):
        """Test response when clarification needed."""
        with patch.object(SessionManager, '__init__', lambda x, y: None):
            manager = SessionManager(mock_redis)
            manager.intent_extractor = MagicMock()

            session = AgentCreationSession(
                tenant_id="tenant-1",
                user_id="user-1",
                accumulated_intents=IntentExtractionResult(
                    original_input="test",
                    normalized_input="test",
                    needs_clarification=True,
                    clarification_questions=["What system should be used?"],
                ),
            )

            response = await manager._generate_response(session)

            assert "more information" in response
            assert "What system should be used?" in response
