"""Registry of available capabilities."""

import structlog

from aswa_agents.generation.capabilities import Capability, CapabilityCategory
from aswa_agents.generation.models import IntentType

logger = structlog.get_logger()


class CapabilityRegistry:
    """Singleton registry of all available capabilities."""

    _instance: "CapabilityRegistry | None" = None
    _capabilities: dict[str, Capability] = {}
    _initialized: bool = False

    def __new__(cls) -> "CapabilityRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def initialize(cls) -> None:
        """Initialize with built-in capabilities."""
        if cls._initialized:
            return

        logger.info("Initializing capability registry")

        cls._register_trigger_capabilities()
        cls._register_ai_capabilities()
        cls._register_integration_capabilities()
        cls._register_logic_capabilities()

        cls._initialized = True
        logger.info("Capability registry initialized", capability_count=len(cls._capabilities))

    @classmethod
    def _register_trigger_capabilities(cls) -> None:
        """Register trigger capabilities."""
        triggers = [
            Capability(
                id="trigger_email",
                name="Email Trigger",
                description="Trigger when an email is received",
                category=CapabilityCategory.TRIGGER,
                intent_types=[IntentType.TRIGGER_ON_EMAIL.value],
                required_connectors=["email"],
                parameter_schema={
                    "inbox": {"type": "string", "description": "Email inbox to monitor"},
                    "from_filter": {"type": "string", "description": "Filter by sender"},
                    "subject_filter": {"type": "string", "description": "Filter by subject"},
                },
                examples=["When I receive an email", "When an email arrives in support@", "On new email from customers"],
            ),
            Capability(
                id="trigger_slack",
                name="Slack Message Trigger",
                description="Trigger on Slack messages",
                category=CapabilityCategory.TRIGGER,
                intent_types=[IntentType.TRIGGER_ON_SLACK.value],
                required_connectors=["slack"],
                parameter_schema={
                    "channel": {"type": "string", "description": "Slack channel to monitor"},
                    "keyword": {"type": "string", "description": "Keyword to match"},
                },
                examples=["When someone posts in #support", "On Slack message mentioning 'urgent'"],
            ),
            Capability(
                id="trigger_document",
                name="Document Trigger",
                description="Trigger when a document is uploaded or updated",
                category=CapabilityCategory.TRIGGER,
                intent_types=[IntentType.TRIGGER_ON_DOCUMENT.value],
                required_connectors=[],
                parameter_schema={
                    "source": {"type": "string", "description": "Document source"},
                    "file_type": {"type": "string", "description": "File type filter"},
                },
                examples=["When a document is uploaded", "When a new PDF is added"],
            ),
            Capability(
                id="trigger_schedule",
                name="Schedule Trigger",
                description="Trigger on a schedule",
                category=CapabilityCategory.TRIGGER,
                intent_types=[IntentType.TRIGGER_ON_SCHEDULE.value],
                required_connectors=[],
                parameter_schema={"schedule": {"type": "string", "description": "Cron expression or natural language"}},
                examples=["Every day at 9am", "Weekly on Monday", "Every hour"],
            ),
            Capability(
                id="trigger_webhook",
                name="Webhook Trigger",
                description="Trigger on incoming webhook",
                category=CapabilityCategory.TRIGGER,
                intent_types=[IntentType.TRIGGER_ON_WEBHOOK.value],
                required_connectors=[],
                parameter_schema={"path": {"type": "string", "description": "Webhook path"}},
                examples=["When I call a webhook", "On external API call"],
            ),
            Capability(
                id="trigger_insight",
                name="Insight Trigger",
                description="Trigger when an insight is detected",
                category=CapabilityCategory.TRIGGER,
                intent_types=[IntentType.TRIGGER_ON_INSIGHT.value],
                required_connectors=[],
                parameter_schema={
                    "insight_type": {"type": "string", "description": "Type of insight"},
                    "confidence_threshold": {"type": "number", "description": "Minimum confidence"},
                },
                examples=["When a bug is detected", "When a feature request is identified"],
            ),
        ]

        for cap in triggers:
            cls._capabilities[cap.id] = cap

    @classmethod
    def _register_ai_capabilities(cls) -> None:
        """Register AI action capabilities."""
        ai_caps = [
            Capability(
                id="action_summarize",
                name="Summarize",
                description="Summarize content using AI",
                category=CapabilityCategory.AI,
                intent_types=[IntentType.ACTION_SUMMARIZE.value],
                required_connectors=[],
                parameter_schema={
                    "max_length": {"type": "integer", "description": "Maximum summary length"},
                    "style": {"type": "string", "enum": ["brief", "detailed", "bullet_points"]},
                },
                examples=["Summarize the email", "Create a brief summary", "Generate a TL;DR"],
            ),
            Capability(
                id="action_extract",
                name="Extract Information",
                description="Extract specific information from content",
                category=CapabilityCategory.AI,
                intent_types=[IntentType.ACTION_EXTRACT.value],
                required_connectors=[],
                parameter_schema={
                    "extract_type": {"type": "string", "enum": ["entities", "action_items", "dates", "custom"]},
                    "custom_fields": {"type": "array", "description": "Custom fields to extract"},
                },
                examples=["Extract action items", "Find all dates mentioned", "Extract customer name and issue"],
            ),
            Capability(
                id="action_search",
                name="Search Knowledge Base",
                description="Search the knowledge base for relevant information",
                category=CapabilityCategory.AI,
                intent_types=[IntentType.ACTION_SEARCH.value],
                required_connectors=[],
                parameter_schema={
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "description": "Max results"},
                },
                examples=["Search for similar issues", "Find related documentation"],
            ),
        ]

        for cap in ai_caps:
            cls._capabilities[cap.id] = cap

    @classmethod
    def _register_integration_capabilities(cls) -> None:
        """Register integration action capabilities."""
        integration_caps = [
            Capability(
                id="action_create_jira",
                name="Create Jira Ticket",
                description="Create a Jira ticket",
                category=CapabilityCategory.INTEGRATION,
                intent_types=[IntentType.ACTION_CREATE_TICKET.value],
                required_connectors=["jira"],
                parameter_schema={
                    "project": {"type": "string", "required": True},
                    "issue_type": {"type": "string", "default": "Task"},
                    "priority": {"type": "string"},
                    "assignee": {"type": "string"},
                },
                examples=["Create a Jira ticket", "Open a bug in Jira", "Create an issue in PROJECT"],
            ),
            Capability(
                id="action_create_linear",
                name="Create Linear Issue",
                description="Create a Linear issue",
                category=CapabilityCategory.INTEGRATION,
                intent_types=[IntentType.ACTION_CREATE_TICKET.value],
                required_connectors=["linear"],
                parameter_schema={
                    "team": {"type": "string", "required": True},
                    "priority": {"type": "integer"},
                },
                examples=["Create a Linear issue", "Add to Linear backlog"],
            ),
            Capability(
                id="action_send_slack",
                name="Send Slack Message",
                description="Send a message to Slack",
                category=CapabilityCategory.NOTIFICATION,
                intent_types=[IntentType.ACTION_SEND_MESSAGE.value],
                required_connectors=["slack"],
                parameter_schema={
                    "channel": {"type": "string", "required": True},
                    "message": {"type": "string", "required": True},
                    "thread_reply": {"type": "boolean", "default": False},
                },
                examples=["Post to Slack", "Send message to #channel", "Notify the team on Slack"],
            ),
            Capability(
                id="action_send_email",
                name="Send Email",
                description="Send an email",
                category=CapabilityCategory.NOTIFICATION,
                intent_types=[IntentType.ACTION_SEND_EMAIL.value],
                required_connectors=["email"],
                parameter_schema={
                    "to": {"type": "string", "required": True},
                    "subject": {"type": "string", "required": True},
                    "body": {"type": "string", "required": True},
                },
                examples=["Send an email", "Email the customer", "Reply to the sender"],
            ),
            Capability(
                id="action_webhook",
                name="Call Webhook",
                description="Call an external webhook",
                category=CapabilityCategory.INTEGRATION,
                intent_types=[IntentType.ACTION_CALL_WEBHOOK.value],
                required_connectors=[],
                parameter_schema={
                    "url": {"type": "string", "required": True},
                    "method": {"type": "string", "default": "POST"},
                    "headers": {"type": "object"},
                    "body": {"type": "object"},
                },
                examples=["Call a webhook", "POST to external API", "Trigger external system"],
            ),
        ]

        for cap in integration_caps:
            cls._capabilities[cap.id] = cap

    @classmethod
    def _register_logic_capabilities(cls) -> None:
        """Register logic capabilities."""
        logic_caps = [
            Capability(
                id="logic_condition",
                name="Condition",
                description="Execute actions conditionally",
                category=CapabilityCategory.LOGIC,
                intent_types=[IntentType.CONDITION_FILTER.value, IntentType.CONDITION_MATCH.value],
                required_connectors=[],
                parameter_schema={
                    "condition": {"type": "string", "required": True},
                    "if_true": {"type": "array"},
                    "if_false": {"type": "array"},
                },
                examples=["If the email is from VIP", "When priority is high", "Only if contains 'urgent'"],
            ),
        ]

        for cap in logic_caps:
            cls._capabilities[cap.id] = cap

    @classmethod
    def get_capability(cls, capability_id: str) -> Capability | None:
        """Get capability by ID."""
        return cls._capabilities.get(capability_id)

    @classmethod
    def get_all_capabilities(cls) -> list[Capability]:
        """Get all registered capabilities."""
        return list(cls._capabilities.values())

    @classmethod
    def get_capabilities_for_intent(cls, intent_type: str) -> list[Capability]:
        """Get capabilities that can handle an intent type."""
        return [cap for cap in cls._capabilities.values() if intent_type in cap.intent_types]

    @classmethod
    def get_capabilities_by_category(cls, category: CapabilityCategory) -> list[Capability]:
        """Get capabilities by category."""
        return [cap for cap in cls._capabilities.values() if cap.category == category]

    @classmethod
    def clear(cls) -> None:
        """Clear registry. For testing only."""
        cls._capabilities.clear()
        cls._initialized = False
