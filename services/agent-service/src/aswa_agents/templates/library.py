"""Agent templates library and engine."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
import structlog

logger = structlog.get_logger()


class TemplateCategory(str, Enum):
    """Categories of agent templates."""

    COMMUNICATION = "communication"
    PRODUCTIVITY = "productivity"
    ANALYTICS = "analytics"
    COMPLIANCE = "compliance"
    INTEGRATION = "integration"
    CUSTOM = "custom"


class TemplateVisibility(str, Enum):
    """Visibility of a template."""

    PUBLIC = "public"  # Available to all tenants
    PRIVATE = "private"  # Only for specific tenant
    SHARED = "shared"  # Shared with specific tenants


class TemplateVariable(BaseModel):
    """A variable that can be customized in a template."""

    name: str
    display_name: str
    description: str = ""
    type: str = "string"  # string, number, boolean, select, array
    required: bool = True
    default: Any = None
    options: list[str] | None = None  # For select type
    validation_pattern: str | None = None


class AgentTemplate(BaseModel):
    """A reusable agent template."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    display_name: str
    description: str
    category: TemplateCategory
    visibility: TemplateVisibility = TemplateVisibility.PUBLIC
    owner_tenant_id: UUID | None = None

    # Template content
    definition: dict[str, Any] = Field(default_factory=dict)
    variables: list[TemplateVariable] = Field(default_factory=list)

    # Metadata
    icon: str = "zap"
    tags: list[str] = Field(default_factory=list)
    use_count: int = 0
    rating: float = 0.0
    rating_count: int = 0

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: UUID | None = None


class TemplateInstance(BaseModel):
    """An instance created from a template."""

    id: UUID = Field(default_factory=uuid4)
    template_id: UUID
    template_version: int = 1
    agent_id: UUID | None = None  # Created agent
    variable_values: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: UUID


# Built-in templates
BUILTIN_TEMPLATES = [
    AgentTemplate(
        id=uuid4(),
        name="email-summarizer",
        display_name="Email Summarizer",
        description="Summarize incoming emails and send key points to Slack",
        category=TemplateCategory.COMMUNICATION,
        visibility=TemplateVisibility.PUBLIC,
        icon="mail",
        tags=["email", "slack", "summarization"],
        definition={
            "trigger": {
                "type": "email",
                "name": "Email Received",
                "config": {"inbox": "{{email_inbox}}"},
            },
            "actions": [
                {
                    "id": "summarize",
                    "type": "summarize",
                    "name": "Summarize Email",
                    "config": {"style": "{{summary_style}}", "max_length": 500},
                },
                {
                    "id": "notify",
                    "type": "send_slack",
                    "name": "Send to Slack",
                    "config": {"channel": "{{slack_channel}}"},
                    "depends_on": ["summarize"],
                },
            ],
        },
        variables=[
            TemplateVariable(
                name="email_inbox",
                display_name="Email Inbox",
                description="Email address to monitor",
                type="string",
                required=True,
            ),
            TemplateVariable(
                name="summary_style",
                display_name="Summary Style",
                description="How to format the summary",
                type="select",
                options=["brief", "detailed", "bullet_points"],
                default="brief",
            ),
            TemplateVariable(
                name="slack_channel",
                display_name="Slack Channel",
                description="Channel to post summaries",
                type="string",
                required=True,
                default="#general",
            ),
        ],
    ),
    AgentTemplate(
        id=uuid4(),
        name="risk-alert",
        display_name="Risk Alert",
        description="Monitor for risks in documents and alert stakeholders",
        category=TemplateCategory.COMPLIANCE,
        visibility=TemplateVisibility.PUBLIC,
        icon="alert-triangle",
        tags=["risk", "compliance", "notification"],
        definition={
            "trigger": {
                "type": "insight",
                "name": "Risk Detected",
                "config": {"insight_type": "risk", "min_severity": "{{min_severity}}"},
            },
            "conditions": [
                {
                    "expression": "confidence > {{confidence_threshold}}",
                    "description": "High confidence risks only",
                }
            ],
            "actions": [
                {
                    "id": "notify_email",
                    "type": "send_email",
                    "name": "Email Alert",
                    "config": {
                        "to": "{{alert_email}}",
                        "subject_template": "Risk Alert: {{risk.title}}",
                        "body_template": "{{risk.description}}\n\nConfidence: {{risk.confidence}}%",
                    },
                },
                {
                    "id": "create_ticket",
                    "type": "create_ticket",
                    "name": "Create Ticket",
                    "config": {
                        "project": "{{ticket_project}}",
                        "issue_type": "bug",
                        "priority": "{{risk.severity}}",
                    },
                    "depends_on": ["notify_email"],
                },
            ],
        },
        variables=[
            TemplateVariable(
                name="min_severity",
                display_name="Minimum Severity",
                description="Minimum severity level to trigger",
                type="select",
                options=["low", "medium", "high", "critical"],
                default="medium",
            ),
            TemplateVariable(
                name="confidence_threshold",
                display_name="Confidence Threshold",
                description="Minimum confidence score (0-1)",
                type="number",
                default=0.7,
            ),
            TemplateVariable(
                name="alert_email",
                display_name="Alert Email",
                description="Email to send alerts to",
                type="string",
                required=True,
            ),
            TemplateVariable(
                name="ticket_project",
                display_name="Ticket Project",
                description="Project for created tickets",
                type="string",
                required=False,
            ),
        ],
    ),
    AgentTemplate(
        id=uuid4(),
        name="weekly-digest",
        display_name="Weekly Digest",
        description="Generate and send weekly summary of insights",
        category=TemplateCategory.ANALYTICS,
        visibility=TemplateVisibility.PUBLIC,
        icon="calendar",
        tags=["digest", "schedule", "summary"],
        definition={
            "trigger": {
                "type": "schedule",
                "name": "Weekly Schedule",
                "config": {"frequency": "weekly", "day": "{{digest_day}}", "time": "{{digest_time}}"},
            },
            "actions": [
                {
                    "id": "aggregate",
                    "type": "aggregate",
                    "name": "Aggregate Insights",
                    "config": {"operation": "group", "group_by": "type"},
                },
                {
                    "id": "summarize",
                    "type": "summarize",
                    "name": "Create Summary",
                    "config": {"style": "detailed"},
                    "depends_on": ["aggregate"],
                },
                {
                    "id": "send",
                    "type": "send_email",
                    "name": "Send Digest",
                    "config": {
                        "to": "{{recipients}}",
                        "subject_template": "Weekly Insights Digest",
                        "body_template": "{{summary}}",
                    },
                    "depends_on": ["summarize"],
                },
            ],
        },
        variables=[
            TemplateVariable(
                name="digest_day",
                display_name="Day of Week",
                description="Day to send the digest",
                type="select",
                options=["monday", "tuesday", "wednesday", "thursday", "friday"],
                default="monday",
            ),
            TemplateVariable(
                name="digest_time",
                display_name="Time",
                description="Time to send (24h format)",
                type="string",
                default="09:00",
            ),
            TemplateVariable(
                name="recipients",
                display_name="Recipients",
                description="Email recipients (comma-separated)",
                type="string",
                required=True,
            ),
        ],
    ),
]


class TemplateLibrary:
    """Manages agent templates."""

    def __init__(self, tenant_id: UUID):
        self.tenant_id = tenant_id
        self._templates: dict[UUID, AgentTemplate] = {}
        self._instances: dict[UUID, TemplateInstance] = {}
        self._logger = logger.bind(
            component="TemplateLibrary",
            tenant_id=str(tenant_id),
        )

        # Load builtin templates
        for template in BUILTIN_TEMPLATES:
            self._templates[template.id] = template

    async def get_templates(
        self,
        category: TemplateCategory | None = None,
        search: str | None = None,
        tags: list[str] | None = None,
    ) -> list[AgentTemplate]:
        """Get available templates."""
        templates = []

        for template in self._templates.values():
            # Check visibility
            if template.visibility == TemplateVisibility.PRIVATE:
                if template.owner_tenant_id != self.tenant_id:
                    continue
            elif template.visibility == TemplateVisibility.SHARED:
                # Check if tenant has access (would need access list)
                pass

            # Filter by category
            if category and template.category != category:
                continue

            # Filter by search
            if search:
                search_lower = search.lower()
                if (
                    search_lower not in template.name.lower()
                    and search_lower not in template.display_name.lower()
                    and search_lower not in template.description.lower()
                ):
                    continue

            # Filter by tags
            if tags:
                if not any(tag in template.tags for tag in tags):
                    continue

            templates.append(template)

        return sorted(templates, key=lambda t: t.use_count, reverse=True)

    async def get_template(self, template_id: UUID) -> AgentTemplate | None:
        """Get a specific template."""
        return self._templates.get(template_id)

    async def create_template(
        self,
        template: AgentTemplate,
        created_by: UUID,
    ) -> AgentTemplate:
        """Create a new template."""
        template.owner_tenant_id = self.tenant_id
        template.created_by = created_by
        template.created_at = datetime.now(timezone.utc)
        template.updated_at = datetime.now(timezone.utc)

        self._templates[template.id] = template

        self._logger.info(
            "Template created",
            template_id=str(template.id),
            template_name=template.name,
        )

        return template

    async def update_template(
        self,
        template_id: UUID,
        updates: dict[str, Any],
    ) -> AgentTemplate:
        """Update a template."""
        template = self._templates.get(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        if template.owner_tenant_id != self.tenant_id:
            raise PermissionError("Cannot update template owned by another tenant")

        for key, value in updates.items():
            if hasattr(template, key):
                setattr(template, key, value)

        template.updated_at = datetime.now(timezone.utc)

        return template

    async def delete_template(self, template_id: UUID) -> None:
        """Delete a template."""
        template = self._templates.get(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        if template.owner_tenant_id != self.tenant_id:
            raise PermissionError("Cannot delete template owned by another tenant")

        del self._templates[template_id]

        self._logger.info(
            "Template deleted",
            template_id=str(template_id),
        )


class TemplateEngine:
    """Renders templates into agent definitions."""

    def __init__(self):
        self._logger = logger.bind(component="TemplateEngine")

    def render(
        self,
        template: AgentTemplate,
        variable_values: dict[str, Any],
    ) -> dict[str, Any]:
        """Render a template with variable values."""
        # Validate required variables
        errors = self.validate_variables(template, variable_values)
        if errors:
            raise ValueError(f"Invalid variables: {', '.join(errors)}")

        # Apply defaults
        values = self._apply_defaults(template, variable_values)

        # Render definition
        definition = self._render_dict(template.definition, values)

        return definition

    def validate_variables(
        self,
        template: AgentTemplate,
        values: dict[str, Any],
    ) -> list[str]:
        """Validate variable values against template schema."""
        errors = []

        for variable in template.variables:
            value = values.get(variable.name)

            if variable.required and value is None and variable.default is None:
                errors.append(f"Missing required variable: {variable.name}")
                continue

            if value is not None:
                # Type validation
                if variable.type == "number":
                    if not isinstance(value, (int, float)):
                        errors.append(f"{variable.name} must be a number")
                elif variable.type == "boolean":
                    if not isinstance(value, bool):
                        errors.append(f"{variable.name} must be a boolean")
                elif variable.type == "select":
                    if variable.options and value not in variable.options:
                        errors.append(f"{variable.name} must be one of: {variable.options}")
                elif variable.type == "array":
                    if not isinstance(value, list):
                        errors.append(f"{variable.name} must be an array")

                # Pattern validation
                if variable.validation_pattern and isinstance(value, str):
                    import re
                    if not re.match(variable.validation_pattern, value):
                        errors.append(f"{variable.name} does not match pattern")

        return errors

    def _apply_defaults(
        self,
        template: AgentTemplate,
        values: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply default values for missing variables."""
        result = {}

        for variable in template.variables:
            if variable.name in values:
                result[variable.name] = values[variable.name]
            elif variable.default is not None:
                result[variable.name] = variable.default

        return result

    def _render_dict(
        self,
        data: dict[str, Any],
        values: dict[str, Any],
    ) -> dict[str, Any]:
        """Recursively render dictionary with variable substitution."""
        result = {}

        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self._render_string(value, values)
            elif isinstance(value, dict):
                result[key] = self._render_dict(value, values)
            elif isinstance(value, list):
                result[key] = [
                    self._render_dict(item, values) if isinstance(item, dict)
                    else self._render_string(item, values) if isinstance(item, str)
                    else item
                    for item in value
                ]
            else:
                result[key] = value

        return result

    def _render_string(self, text: str, values: dict[str, Any]) -> str:
        """Render string with variable substitution."""
        import re

        def replace_var(match: re.Match) -> str:
            var_path = match.group(1)

            # Handle nested paths like risk.title
            parts = var_path.split(".")
            value = values

            for part in parts:
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    return match.group(0)  # Keep original if not found

            return str(value) if value is not None else match.group(0)

        return re.sub(r"\{\{(\w+(?:\.\w+)*)\}\}", replace_var, text)

    def preview(
        self,
        template: AgentTemplate,
        variable_values: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Preview template with optional values, showing placeholders."""
        values = variable_values or {}

        # For preview, use display names as placeholders
        for variable in template.variables:
            if variable.name not in values:
                values[variable.name] = f"[{variable.display_name}]"

        return self._render_dict(template.definition, values)
