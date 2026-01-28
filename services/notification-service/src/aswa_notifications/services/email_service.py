from typing import Any
import structlog

from aswa_notifications.channels.email import EmailChannel, EmailTemplateBuilder
from aswa_notifications.services.notification_service import NotificationService
from aswa_notifications.models.notification import (
    NotificationCreate,
    NotificationType,
    NotificationChannel,
    NotificationPriority,
)

logger = structlog.get_logger()


class EmailService:
    """High-level email service."""

    def __init__(
        self,
        notification_service: NotificationService,
    ):
        """Initialize email service.

        Args:
            notification_service: Core notification service
        """
        self.notification_service = notification_service

    async def send_insight_alert(
        self,
        tenant_id: str,
        user_id: str,
        insight: dict[str, Any],
        view_url: str | None = None,
    ) -> None:
        """Send insight alert email.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            insight: Insight data
            view_url: URL to view insight
        """
        # Build HTML content
        html_content = EmailTemplateBuilder.insight_alert(
            insight_title=insight.get("title", "Untitled"),
            insight_type=insight.get("type", "insight"),
            severity=insight.get("severity", "medium"),
            confidence=insight.get("confidence", 0),
            description=insight.get("description", ""),
            document_name=insight.get("document_name"),
            view_url=view_url or "#",
        )

        # Build plain text
        plain_text = f"""
New {insight.get("type", "insight").title()} Identified

{insight.get("title", "Untitled")}
Severity: {insight.get("severity", "medium").title()}
Confidence: {insight.get("confidence", 0):.0%}

{insight.get("description", "")}

View details: {view_url or "N/A"}
"""

        notification = NotificationCreate(
            user_id=user_id,
            type=NotificationType.INSIGHT_ALERT,
            channel=NotificationChannel.EMAIL,
            priority=self._severity_to_priority(insight.get("severity")),
            subject=f"New {insight.get('type', 'insight').title()}: {insight.get('title', 'Untitled')}",
            content={
                "body": plain_text,
                "html": html_content,
            },
            metadata={"insight_id": insight.get("id")},
        )

        await self.notification_service.send(tenant_id, notification)

    async def send_daily_digest(
        self,
        tenant_id: str,
        user_id: str,
        digest_data: dict[str, Any],
        view_url: str | None = None,
    ) -> None:
        """Send daily digest email.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            digest_data: Digest data
            view_url: Dashboard URL
        """
        html_content = EmailTemplateBuilder.digest(
            period="daily",
            date_range=digest_data.get("date_range", "Today"),
            summary=digest_data.get("summary", "Here's your daily summary."),
            new_insights=digest_data.get("new_insights", 0),
            new_risks=digest_data.get("new_risks", 0),
            new_opportunities=digest_data.get("new_opportunities", 0),
            documents_processed=digest_data.get("documents_processed", 0),
            top_items=digest_data.get("top_items", []),
            view_url=view_url or "#",
        )

        plain_text = self._build_digest_plain_text(digest_data, "daily")

        notification = NotificationCreate(
            user_id=user_id,
            type=NotificationType.DIGEST,
            channel=NotificationChannel.EMAIL,
            priority=NotificationPriority.LOW,
            subject=f"Your Daily ASWA Digest - {digest_data.get('date_range', 'Today')}",
            content={
                "body": plain_text,
                "html": html_content,
            },
        )

        await self.notification_service.send(tenant_id, notification)

    async def send_weekly_digest(
        self,
        tenant_id: str,
        user_id: str,
        digest_data: dict[str, Any],
        view_url: str | None = None,
    ) -> None:
        """Send weekly digest email.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            digest_data: Digest data
            view_url: Dashboard URL
        """
        html_content = EmailTemplateBuilder.digest(
            period="weekly",
            date_range=digest_data.get("date_range", "This Week"),
            summary=digest_data.get("summary", "Here's your weekly summary."),
            new_insights=digest_data.get("new_insights", 0),
            new_risks=digest_data.get("new_risks", 0),
            new_opportunities=digest_data.get("new_opportunities", 0),
            documents_processed=digest_data.get("documents_processed", 0),
            top_items=digest_data.get("top_items", []),
            view_url=view_url or "#",
        )

        plain_text = self._build_digest_plain_text(digest_data, "weekly")

        notification = NotificationCreate(
            user_id=user_id,
            type=NotificationType.DIGEST,
            channel=NotificationChannel.EMAIL,
            priority=NotificationPriority.LOW,
            subject=f"Your Weekly ASWA Digest - {digest_data.get('date_range', 'This Week')}",
            content={
                "body": plain_text,
                "html": html_content,
            },
        )

        await self.notification_service.send(tenant_id, notification)

    async def send_document_processed(
        self,
        tenant_id: str,
        user_id: str,
        document: dict[str, Any],
        view_url: str | None = None,
    ) -> None:
        """Send document processed email.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            document: Document data
            view_url: Document view URL
        """
        html_content = EmailTemplateBuilder.document_processed(
            document_name=document.get("name", "Unknown"),
            insight_count=document.get("insight_count", 0),
            processing_time=document.get("processing_time", "N/A"),
            risk_count=document.get("risk_count", 0),
            opportunity_count=document.get("opportunity_count", 0),
            view_url=view_url or "#",
        )

        plain_text = f"""
Document Processing Complete

{document.get("name", "Unknown")} has been processed successfully.

Insights Found: {document.get("insight_count", 0)}
Risks: {document.get("risk_count", 0)}
Opportunities: {document.get("opportunity_count", 0)}
Processing Time: {document.get("processing_time", "N/A")}

View document: {view_url or "N/A"}
"""

        notification = NotificationCreate(
            user_id=user_id,
            type=NotificationType.DOCUMENT_PROCESSED,
            channel=NotificationChannel.EMAIL,
            priority=NotificationPriority.NORMAL,
            subject=f"Document Processed: {document.get('name', 'Unknown')}",
            content={
                "body": plain_text,
                "html": html_content,
            },
            metadata={"document_id": document.get("id")},
        )

        await self.notification_service.send(tenant_id, notification)

    async def send_document_failed(
        self,
        tenant_id: str,
        user_id: str,
        document: dict[str, Any],
        error: str,
        retry_url: str | None = None,
    ) -> None:
        """Send document failed email.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            document: Document data
            error: Error message
            retry_url: Retry URL
        """
        html_content = EmailTemplateBuilder.document_failed(
            document_name=document.get("name", "Unknown"),
            error_message=error,
            retry_url=retry_url or "#",
        )

        plain_text = f"""
Document Processing Failed

{document.get("name", "Unknown")} could not be processed.

Error: {error}

Please try uploading the document again or contact support for assistance.
"""

        notification = NotificationCreate(
            user_id=user_id,
            type=NotificationType.DOCUMENT_FAILED,
            channel=NotificationChannel.EMAIL,
            priority=NotificationPriority.HIGH,
            subject=f"Processing Failed: {document.get('name', 'Unknown')}",
            content={
                "body": plain_text,
                "html": html_content,
            },
            metadata={"document_id": document.get("id")},
        )

        await self.notification_service.send(tenant_id, notification)

    def _severity_to_priority(
        self,
        severity: str | None,
    ) -> NotificationPriority:
        """Map severity to notification priority.

        Args:
            severity: Insight severity

        Returns:
            Notification priority
        """
        mapping = {
            "critical": NotificationPriority.URGENT,
            "high": NotificationPriority.HIGH,
            "medium": NotificationPriority.NORMAL,
            "low": NotificationPriority.LOW,
        }
        return mapping.get(severity or "medium", NotificationPriority.NORMAL)

    def _build_digest_plain_text(
        self,
        digest_data: dict[str, Any],
        period: str,
    ) -> str:
        """Build plain text digest.

        Args:
            digest_data: Digest data
            period: Digest period

        Returns:
            Plain text content
        """
        lines = [
            f"Your {period.title()} ASWA Digest",
            f"{digest_data.get('date_range', '')}",
            "",
            digest_data.get("summary", ""),
            "",
            "Summary:",
            f"- New Insights: {digest_data.get('new_insights', 0)}",
            f"- Risks: {digest_data.get('new_risks', 0)}",
            f"- Opportunities: {digest_data.get('new_opportunities', 0)}",
            f"- Documents Processed: {digest_data.get('documents_processed', 0)}",
        ]

        top_items = digest_data.get("top_items", [])
        if top_items:
            lines.append("")
            lines.append("Top Insights:")
            for item in top_items[:5]:
                lines.append(f"- {item.get('title', 'Untitled')} ({item.get('type', 'N/A')})")

        return "\n".join(lines)
