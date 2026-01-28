from pathlib import Path
from typing import Any
from jinja2 import Environment, FileSystemLoader, select_autoescape
import structlog

from aswa_notifications.config import get_settings

logger = structlog.get_logger()


class TemplateService:
    """Manages notification templates."""

    def __init__(self):
        self.settings = get_settings()
        self._env: Environment | None = None
        self._templates: dict[str, dict] = {}

    def initialize(self) -> None:
        """Initialize the template service."""
        template_dir = Path(self.settings.template_dir)

        self._env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )

        # Register custom filters
        self._env.filters["format_date"] = self._format_date
        self._env.filters["format_number"] = self._format_number

        logger.info("Template service initialized", template_dir=str(template_dir))

    def _format_date(self, value, format="%B %d, %Y"):
        """Format a date."""
        if isinstance(value, str):
            from datetime import datetime
            value = datetime.fromisoformat(value)
        return value.strftime(format)

    def _format_number(self, value, decimals=0):
        """Format a number."""
        if decimals == 0:
            return f"{int(value):,}"
        return f"{value:,.{decimals}f}"

    def render(
        self,
        template_id: str,
        data: dict[str, Any],
        channel: str = "email",
    ) -> dict[str, str]:
        """Render a template.

        Args:
            template_id: Template identifier
            data: Template data
            channel: Target channel

        Returns:
            Rendered content dict with 'subject', 'body', 'html' keys
        """
        if not self._env:
            self.initialize()

        result = {}

        # Render subject
        try:
            subject_template = self._env.get_template(
                f"{channel}/{template_id}/subject.txt"
            )
            result["subject"] = subject_template.render(**data).strip()
        except Exception:
            result["subject"] = data.get("subject", "Notification")

        # Render plain text body
        try:
            body_template = self._env.get_template(
                f"{channel}/{template_id}/body.txt"
            )
            result["body"] = body_template.render(**data)
        except Exception:
            result["body"] = str(data.get("content", ""))

        # Render HTML body (email only)
        if channel == "email":
            try:
                html_template = self._env.get_template(
                    f"{channel}/{template_id}/body.html"
                )
                result["html"] = html_template.render(**data)
            except Exception:
                result["html"] = None

        return result

    def get_template_info(
        self,
        template_id: str,
    ) -> dict[str, Any] | None:
        """Get template metadata.

        Args:
            template_id: Template identifier

        Returns:
            Template metadata or None
        """
        return self._templates.get(template_id)

    def register_template(
        self,
        template_id: str,
        name: str,
        description: str,
        variables: list[str],
        channels: list[str],
    ) -> None:
        """Register a template.

        Args:
            template_id: Template identifier
            name: Template name
            description: Template description
            variables: Required variables
            channels: Supported channels
        """
        self._templates[template_id] = {
            "id": template_id,
            "name": name,
            "description": description,
            "variables": variables,
            "channels": channels,
        }


# Default templates
DEFAULT_TEMPLATES = {
    "insight_alert": {
        "name": "Insight Alert",
        "description": "Alert for new or updated insights",
        "variables": ["insight_title", "insight_type", "severity", "confidence", "document_name"],
        "channels": ["email", "push", "in_app"],
    },
    "digest_daily": {
        "name": "Daily Digest",
        "description": "Daily summary of insights and activity",
        "variables": ["date", "new_insights", "top_risks", "top_opportunities", "documents_processed"],
        "channels": ["email"],
    },
    "digest_weekly": {
        "name": "Weekly Digest",
        "description": "Weekly summary of insights and activity",
        "variables": ["start_date", "end_date", "summary", "highlights"],
        "channels": ["email"],
    },
    "document_processed": {
        "name": "Document Processed",
        "description": "Notification when document processing completes",
        "variables": ["document_name", "insight_count", "processing_time"],
        "channels": ["email", "push", "in_app"],
    },
    "document_failed": {
        "name": "Document Processing Failed",
        "description": "Notification when document processing fails",
        "variables": ["document_name", "error_message"],
        "channels": ["email", "push", "in_app"],
    },
}
