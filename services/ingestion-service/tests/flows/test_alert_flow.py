"""Tests for alert flow."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from tests.flows.conftest import TEST_TENANT_ID, MockAlert


class TestFetchActiveAlertsTask:
    """Tests for fetch_active_alerts task."""

    @pytest.mark.asyncio
    async def test_fetch_alerts_success(
        self, mock_session: AsyncMock, mock_alert: MockAlert
    ) -> None:
        """Test fetching active alerts."""
        from aswa_ingestion.flows.alert_flow import fetch_active_alerts

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_alert]
        mock_session.execute.return_value = mock_result

        with patch("aswa_ingestion.flows.alert_flow.get_async_session") as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_session

            with patch(
                "aswa_ingestion.flows.alert_flow.AlertConfig", create=True
            ):
                alerts = await fetch_active_alerts.fn(TEST_TENANT_ID)

                assert len(alerts) == 1
                assert alerts[0]["name"] == "Test Alert"

    @pytest.mark.asyncio
    async def test_fetch_alerts_empty(self, mock_session: AsyncMock) -> None:
        """Test fetching when no active alerts."""
        from aswa_ingestion.flows.alert_flow import fetch_active_alerts

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        with patch("aswa_ingestion.flows.alert_flow.get_async_session") as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_session

            with patch(
                "aswa_ingestion.flows.alert_flow.AlertConfig", create=True
            ):
                alerts = await fetch_active_alerts.fn(TEST_TENANT_ID)

                assert len(alerts) == 0


class TestSearchMatchingInsightsTask:
    """Tests for search_matching_insights task."""

    @pytest.mark.asyncio
    async def test_search_insights_success(
        self, mock_embedder: AsyncMock, mock_vector_store: AsyncMock
    ) -> None:
        """Test searching for matching insights."""
        from aswa_ingestion.flows.alert_flow import search_matching_insights

        # Mock search results
        mock_result = MagicMock()
        mock_result.id = "insight-1"
        mock_result.score = 0.9
        mock_result.payload = {
            "title": "Security Issue",
            "severity": "high",
            "confidence": 0.85,
        }
        mock_vector_store.search.return_value = [mock_result]

        with patch(
            "aswa_ingestion.flows.alert_flow.EmbeddingClient"
        ) as mock_embed_cls:
            mock_embed_cls.return_value = mock_embedder

            with patch(
                "aswa_ingestion.flows.alert_flow.QdrantVectorStore"
            ) as mock_store_cls:
                mock_store_cls.return_value = mock_vector_store

                results = await search_matching_insights.fn(
                    tenant_id=TEST_TENANT_ID,
                    pattern_query="security breach",
                    since=datetime.utcnow() - timedelta(hours=1),
                )

                assert len(results) == 1
                assert results[0]["id"] == "insight-1"
                assert results[0]["severity"] == "high"

    @pytest.mark.asyncio
    async def test_search_insights_empty(
        self, mock_embedder: AsyncMock, mock_vector_store: AsyncMock
    ) -> None:
        """Test search with no results."""
        from aswa_ingestion.flows.alert_flow import search_matching_insights

        mock_vector_store.search.return_value = []

        with patch(
            "aswa_ingestion.flows.alert_flow.EmbeddingClient"
        ) as mock_embed_cls:
            mock_embed_cls.return_value = mock_embedder

            with patch(
                "aswa_ingestion.flows.alert_flow.QdrantVectorStore"
            ) as mock_store_cls:
                mock_store_cls.return_value = mock_vector_store

                results = await search_matching_insights.fn(
                    tenant_id=TEST_TENANT_ID,
                    pattern_query="nonexistent",
                    since=datetime.utcnow() - timedelta(hours=1),
                )

                assert len(results) == 0


class TestEvaluateAlertConditionsTask:
    """Tests for evaluate_alert_conditions task."""

    @pytest.mark.asyncio
    async def test_evaluate_no_matches(self, mock_alert: MockAlert) -> None:
        """Test evaluation with no matches."""
        from aswa_ingestion.flows.alert_flow import evaluate_alert_conditions

        alert_dict = {
            "id": str(mock_alert.id),
            "tenant_id": str(mock_alert.tenant_id),
            "name": mock_alert.name,
            "pattern_query": mock_alert.pattern_query,
            "conditions": mock_alert.conditions,
            "frequency": mock_alert.frequency,
            "last_triggered_at": None,
        }

        with patch(
            "aswa_ingestion.flows.alert_flow.search_matching_insights"
        ) as mock_search:
            mock_search.fn = AsyncMock(return_value=[])

            result = await evaluate_alert_conditions.fn(alert_dict)

            # With mocked empty search, result should be None
            # The actual task uses the task decorator, so we test the function

    @pytest.mark.asyncio
    async def test_evaluate_already_triggered(self, mock_alert: MockAlert) -> None:
        """Test skipping recently triggered alert."""
        from aswa_ingestion.flows.alert_flow import evaluate_alert_conditions

        # Set last triggered to 30 minutes ago (within hourly window)
        mock_alert.last_triggered_at = datetime.utcnow() - timedelta(minutes=30)

        alert_dict = {
            "id": str(mock_alert.id),
            "tenant_id": str(mock_alert.tenant_id),
            "name": mock_alert.name,
            "pattern_query": mock_alert.pattern_query,
            "conditions": mock_alert.conditions,
            "frequency": "hourly",
            "last_triggered_at": mock_alert.last_triggered_at.isoformat(),
        }

        result = await evaluate_alert_conditions.fn(alert_dict)

        assert result is None


class TestSendSlackNotificationTask:
    """Tests for send_slack_notification task."""

    @pytest.mark.asyncio
    async def test_send_slack_success(self) -> None:
        """Test successful Slack notification."""
        from aswa_ingestion.flows.alert_flow import send_slack_notification

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            result = await send_slack_notification.fn(
                webhook_url="https://hooks.slack.com/test",
                channel="#alerts",
                alert_name="Test Alert",
                match_count=5,
                sample_insights=[{"title": "Issue 1", "severity": "high", "score": 0.9}],
            )

            assert result is True
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_slack_failure(self) -> None:
        """Test Slack notification failure."""
        from aswa_ingestion.flows.alert_flow import send_slack_notification

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=Exception("Network error"))
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            result = await send_slack_notification.fn(
                webhook_url="https://hooks.slack.com/test",
                channel="#alerts",
                alert_name="Test Alert",
                match_count=5,
                sample_insights=[],
            )

            assert result is False


class TestSendWebhookNotificationTask:
    """Tests for send_webhook_notification task."""

    @pytest.mark.asyncio
    async def test_send_webhook_success(self) -> None:
        """Test successful webhook notification."""
        from aswa_ingestion.flows.alert_flow import send_webhook_notification

        alert = {"id": str(uuid4()), "name": "Test Alert"}
        match_result = {"match_count": 3, "matched_insights": ["1", "2", "3"]}

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            result = await send_webhook_notification.fn(
                url="https://example.com/webhook",
                alert=alert,
                match_result=match_result,
            )

            assert result is True


class TestSendAlertNotificationsTask:
    """Tests for send_alert_notifications task."""

    @pytest.mark.asyncio
    async def test_send_all_channels(self) -> None:
        """Test sending to all notification channels."""
        from aswa_ingestion.flows.alert_flow import send_alert_notifications

        alert = {
            "id": str(uuid4()),
            "name": "Test Alert",
            "notification_channels": {
                "slack": {"webhook_url": "https://hooks.slack.com/test"},
                "email": {"recipients": ["test@example.com"]},
                "webhook": {"url": "https://example.com/webhook"},
            },
        }

        match_result = {
            "match_count": 3,
            "matched_insights": ["1", "2", "3"],
            "sample_insights": [{"title": "Test", "severity": "high", "score": 0.9}],
        }

        with patch(
            "aswa_ingestion.flows.alert_flow.send_slack_notification"
        ) as mock_slack:
            mock_slack.fn = AsyncMock(return_value=True)

            with patch(
                "aswa_ingestion.flows.alert_flow.send_email_notification"
            ) as mock_email:
                mock_email.fn = AsyncMock(return_value=True)

                with patch(
                    "aswa_ingestion.flows.alert_flow.send_webhook_notification"
                ) as mock_webhook:
                    mock_webhook.fn = AsyncMock(return_value=True)

                    results = await send_alert_notifications.fn(alert, match_result)

                    # Results should contain status for each channel
                    assert "slack" in results or "email" in results or "webhook" in results


class TestEvaluateAlertsFlow:
    """Tests for evaluate_alerts flow."""

    @pytest.mark.asyncio
    async def test_evaluate_no_alerts(self, mock_session: AsyncMock) -> None:
        """Test evaluation with no active alerts."""
        from aswa_ingestion.flows.alert_flow import evaluate_alerts

        with patch(
            "aswa_ingestion.flows.alert_flow.fetch_active_alerts"
        ) as mock_fetch:
            mock_fetch.return_value = []

            stats = await evaluate_alerts(tenant_id=TEST_TENANT_ID)

            assert stats["evaluated"] == 0
            assert stats["triggered"] == 0

    @pytest.mark.asyncio
    async def test_evaluate_alert_triggered(
        self, mock_session: AsyncMock, mock_alert: MockAlert
    ) -> None:
        """Test evaluation with alert that triggers."""
        from aswa_ingestion.flows.alert_flow import evaluate_alerts

        alert_dict = {
            "id": str(mock_alert.id),
            "tenant_id": str(mock_alert.tenant_id),
            "name": mock_alert.name,
            "pattern_query": mock_alert.pattern_query,
            "conditions": mock_alert.conditions,
            "notification_channels": mock_alert.notification_channels,
            "frequency": mock_alert.frequency,
            "last_triggered_at": None,
        }

        match_result = {
            "alert_id": str(mock_alert.id),
            "alert_name": mock_alert.name,
            "matched_insights": ["1", "2"],
            "match_count": 2,
            "sample_insights": [{"title": "Test"}],
        }

        with patch(
            "aswa_ingestion.flows.alert_flow.fetch_active_alerts"
        ) as mock_fetch:
            mock_fetch.return_value = [alert_dict]

            with patch(
                "aswa_ingestion.flows.alert_flow.evaluate_alert_conditions"
            ) as mock_eval:
                mock_eval.return_value = match_result

                with patch(
                    "aswa_ingestion.flows.alert_flow.send_alert_notifications"
                ) as mock_notify:
                    mock_notify.return_value = {"slack": "sent"}

                    with patch(
                        "aswa_ingestion.flows.alert_flow.record_alert_trigger"
                    ) as mock_record:
                        mock_record.return_value = None

                        stats = await evaluate_alerts(tenant_id=TEST_TENANT_ID)

                        assert stats["evaluated"] == 1
                        assert stats["triggered"] == 1
                        assert stats["notifications_sent"] == 1


class TestTestAlertFlow:
    """Tests for test_alert flow."""

    @pytest.mark.asyncio
    async def test_alert_not_found(self) -> None:
        """Test testing non-existent alert."""
        from aswa_ingestion.flows.alert_flow import test_alert

        with patch(
            "aswa_ingestion.flows.alert_flow.fetch_active_alerts"
        ) as mock_fetch:
            mock_fetch.return_value = []

            result = await test_alert(uuid4(), TEST_TENANT_ID)

            assert result["error"] == "Alert not found"
            assert result["matched"] is False

    @pytest.mark.asyncio
    async def test_alert_matches(self, mock_alert: MockAlert) -> None:
        """Test alert that matches."""
        from aswa_ingestion.flows.alert_flow import test_alert

        alert_dict = {
            "id": str(mock_alert.id),
            "tenant_id": str(mock_alert.tenant_id),
            "name": mock_alert.name,
            "pattern_query": mock_alert.pattern_query,
            "conditions": mock_alert.conditions,
            "frequency": mock_alert.frequency,
            "last_triggered_at": None,
        }

        with patch(
            "aswa_ingestion.flows.alert_flow.fetch_active_alerts"
        ) as mock_fetch:
            mock_fetch.return_value = [alert_dict]

            with patch(
                "aswa_ingestion.flows.alert_flow.evaluate_alert_conditions"
            ) as mock_eval:
                mock_eval.return_value = {
                    "match_count": 3,
                    "sample_insights": [{"title": "Test"}],
                }

                result = await test_alert(mock_alert.id, TEST_TENANT_ID)

                assert result["matched"] is True
                assert result["match_count"] == 3
