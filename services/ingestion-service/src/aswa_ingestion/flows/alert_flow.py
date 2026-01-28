"""Alert evaluation and notification flows.

Provides Prefect flows for evaluating alert conditions against
insights and sending notifications through configured channels.
"""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import structlog
from prefect import flow, get_run_logger, task

logger = structlog.get_logger()


# Frequency to time window mapping
FREQUENCY_WINDOWS = {
    "realtime": timedelta(minutes=5),
    "hourly": timedelta(hours=1),
    "daily": timedelta(days=1),
    "weekly": timedelta(weeks=1),
}

# Severity order for comparison
SEVERITY_ORDER = ["info", "low", "medium", "high", "critical"]


@task(name="fetch_active_alerts")
async def fetch_active_alerts(tenant_id: UUID | None = None) -> list[dict[str, Any]]:
    """Fetch all active alert configurations.

    Args:
        tenant_id: Optional tenant filter

    Returns:
        List of alert configuration dicts
    """
    from aswa_common.db import get_async_session
    from sqlalchemy import select

    async with get_async_session() as session:
        # Try to import AlertConfig model
        try:
            from aswa_common.db.models import AlertConfig

            stmt = select(AlertConfig).where(AlertConfig.status == "active")

            if tenant_id:
                stmt = stmt.where(AlertConfig.tenant_id == tenant_id)

            result = await session.execute(stmt)
            alerts = result.scalars().all()

            return [
                {
                    "id": str(alert.id),
                    "tenant_id": str(alert.tenant_id),
                    "name": alert.name,
                    "pattern_query": alert.pattern_query,
                    "conditions": alert.conditions or {},
                    "notification_channels": alert.notification_channels or {},
                    "frequency": alert.frequency or "hourly",
                    "last_triggered_at": (
                        alert.last_triggered_at.isoformat()
                        if alert.last_triggered_at
                        else None
                    ),
                }
                for alert in alerts
            ]
        except ImportError:
            logger.warning("AlertConfig model not available")
            return []


@task(name="search_matching_insights")
async def search_matching_insights(
    tenant_id: UUID,
    pattern_query: str,
    since: datetime,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Search for insights matching the alert pattern.

    Args:
        tenant_id: Tenant ID
        pattern_query: Search query pattern
        since: Start time for search window
        limit: Maximum results

    Returns:
        List of matching insight dicts
    """
    from aswa_ingestion.vectorstore.qdrant import QdrantVectorStore
    from aswa_ingestion.processing.embedder import EmbeddingClient

    try:
        # Generate embedding for the query
        embedder = EmbeddingClient()
        query_vector = await embedder.embed(pattern_query)

        # Search vector store
        vector_store = QdrantVectorStore()
        await vector_store.initialize()

        from aswa_ingestion.vectorstore.base import SearchFilter, FilterOperator

        filters = [
            SearchFilter(
                field="created_at",
                operator=FilterOperator.GTE,
                value=since.isoformat(),
            ),
        ]

        results = await vector_store.search(
            collection="insights",
            query_vector=query_vector,
            limit=limit,
            filters=filters,
            tenant_id=tenant_id,
        )

        return [
            {
                "id": r.id,
                "score": r.score,
                "title": r.payload.get("title", ""),
                "content": r.payload.get("content", ""),
                "severity": r.payload.get("severity", "info"),
                "confidence": r.payload.get("confidence", 0.0),
                "source": r.payload.get("source", ""),
                "created_at": r.payload.get("created_at", ""),
            }
            for r in results
        ]
    except Exception as e:
        logger.warning(f"Failed to search insights: {e}")
        return []


@task(name="evaluate_alert_conditions")
async def evaluate_alert_conditions(
    alert: dict[str, Any],
) -> dict[str, Any] | None:
    """Evaluate if alert conditions are met.

    Args:
        alert: Alert configuration dict

    Returns:
        Match result dict or None if no matches
    """
    prefect_logger = get_run_logger()
    tenant_id = UUID(alert["tenant_id"])

    # Determine time window based on frequency
    frequency = alert.get("frequency", "hourly")
    time_window = FREQUENCY_WINDOWS.get(frequency, timedelta(hours=1))
    since = datetime.utcnow() - time_window

    # Check if already triggered in this window
    if alert.get("last_triggered_at"):
        last_triggered = datetime.fromisoformat(alert["last_triggered_at"])
        if last_triggered > since:
            prefect_logger.debug(
                f"Alert {alert['name']} already triggered in this window"
            )
            return None

    # Search for matching insights
    results = await search_matching_insights(
        tenant_id=tenant_id,
        pattern_query=alert["pattern_query"],
        since=since,
    )

    if not results:
        return None

    # Apply additional conditions
    conditions = alert.get("conditions", {})

    # Filter by severity if specified
    if "min_severity" in conditions:
        min_severity = conditions["min_severity"]
        if min_severity in SEVERITY_ORDER:
            min_idx = SEVERITY_ORDER.index(min_severity)
            results = [
                r
                for r in results
                if SEVERITY_ORDER.index(r.get("severity", "info")) >= min_idx
            ]

    # Filter by confidence if specified
    if "min_confidence" in conditions:
        min_confidence = conditions["min_confidence"]
        results = [
            r for r in results if r.get("confidence", 0) >= min_confidence
        ]

    # Filter by minimum score if specified
    if "min_score" in conditions:
        min_score = conditions["min_score"]
        results = [r for r in results if r.get("score", 0) >= min_score]

    if not results:
        return None

    prefect_logger.info(
        f"Alert '{alert['name']}' matched {len(results)} insights"
    )

    return {
        "alert_id": alert["id"],
        "alert_name": alert["name"],
        "matched_insights": [r["id"] for r in results],
        "match_count": len(results),
        "sample_insights": results[:5],
    }


@task(name="send_slack_notification")
async def send_slack_notification(
    webhook_url: str,
    channel: str | None,
    alert_name: str,
    match_count: int,
    sample_insights: list[dict[str, Any]],
) -> bool:
    """Send Slack notification.

    Args:
        webhook_url: Slack webhook URL
        channel: Optional channel override
        alert_name: Alert name
        match_count: Number of matches
        sample_insights: Sample matching insights

    Returns:
        True if sent successfully
    """
    import httpx

    # Build Slack message
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"🚨 Alert: {alert_name}"},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{match_count}* matching insights found.",
            },
        },
    ]

    # Add sample insights
    for insight in sample_insights[:3]:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"• *{insight.get('title', 'Untitled')}*\n"
                    f"  Severity: {insight.get('severity', 'info')} | "
                    f"  Score: {insight.get('score', 0):.2f}",
                },
            }
        )

    payload: dict[str, Any] = {"blocks": blocks}
    if channel:
        payload["channel"] = channel

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(webhook_url, json=payload, timeout=10)
            return response.status_code == 200
    except Exception as e:
        logger.error(f"Failed to send Slack notification: {e}")
        return False


@task(name="send_email_notification")
async def send_email_notification(
    recipients: list[str],
    subject: str,
    alert_name: str,
    match_count: int,
    sample_insights: list[dict[str, Any]],
) -> bool:
    """Send email notification.

    Args:
        recipients: Email recipients
        subject: Email subject
        alert_name: Alert name
        match_count: Number of matches
        sample_insights: Sample matching insights

    Returns:
        True if sent successfully
    """
    # In production, this would use a real email service (SES, SendGrid, etc.)
    logger.info(
        f"Would send email to {recipients}: "
        f"Alert '{alert_name}' - {match_count} matches"
    )
    return True


@task(name="send_webhook_notification")
async def send_webhook_notification(
    url: str,
    alert: dict[str, Any],
    match_result: dict[str, Any],
) -> bool:
    """Send webhook notification.

    Args:
        url: Webhook URL
        alert: Alert configuration
        match_result: Match result

    Returns:
        True if sent successfully
    """
    import httpx

    payload = {
        "event": "alert_triggered",
        "timestamp": datetime.utcnow().isoformat(),
        "alert": {
            "id": alert["id"],
            "name": alert["name"],
        },
        "matches": {
            "count": match_result["match_count"],
            "insight_ids": match_result["matched_insights"],
        },
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=30)
            return response.status_code in (200, 201, 202)
    except Exception as e:
        logger.error(f"Failed to send webhook notification: {e}")
        return False


@task(name="send_alert_notifications")
async def send_alert_notifications(
    alert: dict[str, Any],
    match_result: dict[str, Any],
) -> dict[str, str]:
    """Send notifications for triggered alert.

    Args:
        alert: Alert configuration
        match_result: Match result with insights

    Returns:
        Dict of channel -> status
    """
    channels = alert.get("notification_channels", {})
    results: dict[str, str] = {}

    # Send to Slack
    if "slack" in channels:
        slack_config = channels["slack"]
        webhook_url = slack_config.get("webhook_url")
        if webhook_url:
            success = await send_slack_notification(
                webhook_url=webhook_url,
                channel=slack_config.get("channel"),
                alert_name=alert["name"],
                match_count=match_result["match_count"],
                sample_insights=match_result["sample_insights"],
            )
            results["slack"] = "sent" if success else "failed"

    # Send email
    if "email" in channels:
        email_config = channels["email"]
        recipients = email_config.get("recipients", [])
        if recipients:
            success = await send_email_notification(
                recipients=recipients,
                subject=f"Alert: {alert['name']}",
                alert_name=alert["name"],
                match_count=match_result["match_count"],
                sample_insights=match_result["sample_insights"],
            )
            results["email"] = "sent" if success else "failed"

    # Send webhook
    if "webhook" in channels:
        webhook_config = channels["webhook"]
        url = webhook_config.get("url")
        if url:
            success = await send_webhook_notification(
                url=url,
                alert=alert,
                match_result=match_result,
            )
            results["webhook"] = "sent" if success else "failed"

    return results


@task(name="record_alert_trigger")
async def record_alert_trigger(
    alert_id: UUID,
    match_result: dict[str, Any],
    notification_results: dict[str, str],
) -> None:
    """Record alert trigger in history.

    Args:
        alert_id: Alert ID
        match_result: Match result
        notification_results: Notification status per channel
    """
    from aswa_common.db import get_async_session
    from sqlalchemy import update

    async with get_async_session() as session:
        try:
            from aswa_common.db.models import AlertHistory, AlertConfig

            # Create history record
            history = AlertHistory(
                alert_config_id=alert_id,
                triggered_at=datetime.utcnow(),
                matched_insight_ids=match_result["matched_insights"],
                notification_status=notification_results,
                match_count=match_result["match_count"],
            )
            session.add(history)

            # Update alert's last triggered time and counter
            stmt = (
                update(AlertConfig)
                .where(AlertConfig.id == alert_id)
                .values(
                    last_triggered_at=datetime.utcnow(),
                    trigger_count=AlertConfig.trigger_count + 1,
                )
            )
            await session.execute(stmt)
            await session.commit()

        except ImportError:
            logger.warning("AlertHistory/AlertConfig models not available")
        except Exception as e:
            logger.error(f"Failed to record alert trigger: {e}")
            await session.rollback()


@flow(
    name="evaluate_alerts",
    description="Evaluate all active alerts and send notifications",
)
async def evaluate_alerts(tenant_id: UUID | None = None) -> dict[str, int]:
    """Main flow to evaluate alerts.

    Should be scheduled to run frequently (e.g., every 5 minutes)
    to check for new matching insights and trigger notifications.

    Args:
        tenant_id: Optional tenant filter

    Returns:
        Statistics dict
    """
    prefect_logger = get_run_logger()
    prefect_logger.info(f"Starting alert evaluation, tenant={tenant_id}")

    stats = {"evaluated": 0, "triggered": 0, "notifications_sent": 0}

    # Fetch active alerts
    alerts = await fetch_active_alerts(tenant_id)
    stats["evaluated"] = len(alerts)

    if not alerts:
        prefect_logger.info("No active alerts to evaluate")
        return stats

    prefect_logger.info(f"Evaluating {len(alerts)} active alerts")

    for alert in alerts:
        # Evaluate conditions
        match_result = await evaluate_alert_conditions(alert)

        if match_result:
            stats["triggered"] += 1
            prefect_logger.info(
                f"Alert triggered: {alert['name']}, "
                f"matches: {match_result['match_count']}"
            )

            # Send notifications
            notification_results = await send_alert_notifications(
                alert, match_result
            )
            stats["notifications_sent"] += sum(
                1 for v in notification_results.values() if v == "sent"
            )

            # Record trigger
            await record_alert_trigger(
                UUID(alert["id"]),
                match_result,
                notification_results,
            )

    prefect_logger.info(f"Alert evaluation completed: {stats}")
    return stats


@flow(
    name="test_alert",
    description="Test an alert configuration without recording trigger",
)
async def test_alert(alert_id: UUID, tenant_id: UUID) -> dict[str, Any]:
    """Test an alert configuration.

    Evaluates the alert without recording trigger or sending
    real notifications (useful for testing alert configuration).

    Args:
        alert_id: Alert ID to test
        tenant_id: Tenant ID

    Returns:
        Test result with matches
    """
    prefect_logger = get_run_logger()
    prefect_logger.info(f"Testing alert {alert_id}")

    # Fetch the specific alert
    alerts = await fetch_active_alerts(tenant_id)
    alert = next((a for a in alerts if a["id"] == str(alert_id)), None)

    if not alert:
        return {"error": "Alert not found", "matched": False}

    # Evaluate without recording
    match_result = await evaluate_alert_conditions(alert)

    return {
        "alert_name": alert["name"],
        "matched": match_result is not None,
        "match_count": match_result["match_count"] if match_result else 0,
        "sample_insights": (
            match_result["sample_insights"] if match_result else []
        ),
    }
