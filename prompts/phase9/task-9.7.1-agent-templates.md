# Task 9.7.1: Agent Templates

## Objective

Implement an agent template system that provides pre-built agent configurations for common use cases, enabling rapid agent creation and standardization.

## Prerequisites

- Task 9.6.x completed (Approval and Permissions)
- Agent definition models

## Implementation

### Step 1: Template Models

```python
# services/agent-service/src/aswa_agents/models/template.py
"""Agent template models."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import Column, String, DateTime, JSON, Text, Boolean, Integer, Index
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from aswa_agents.db.base import Base


class TemplateCategory(str, Enum):
    """Template categories."""

    PRODUCTIVITY = "productivity"
    COMMUNICATION = "communication"
    SUPPORT = "support"
    SALES = "sales"
    HR = "hr"
    IT = "it"
    FINANCE = "finance"
    OPERATIONS = "operations"
    CUSTOM = "custom"


class TemplateVisibility(str, Enum):
    """Template visibility levels."""

    PUBLIC = "public"  # Available to all tenants
    PRIVATE = "private"  # Only creator's tenant
    SHARED = "shared"  # Shared with specific tenants


class AgentTemplateModel(Base):
    """SQLAlchemy model for agent templates."""

    __tablename__ = "agent_templates"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Ownership
    tenant_id = Column(String(100), nullable=True)  # Null for public templates
    created_by = Column(String(100), nullable=True)

    # Template metadata
    name = Column(String(200), nullable=False)
    slug = Column(String(200), nullable=False, unique=True)
    display_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    long_description = Column(Text, nullable=True)
    category = Column(String(50), default=TemplateCategory.CUSTOM.value)

    # Version info
    version = Column(String(20), default="1.0.0")
    is_latest = Column(Boolean, default=True)

    # Content
    definition = Column(JSON, nullable=False)  # Full agent definition
    default_config = Column(JSON, default=dict)  # Default configuration
    required_integrations = Column(JSON, default=list)
    required_permissions = Column(JSON, default=list)

    # Customization
    configurable_fields = Column(JSON, default=list)  # Fields user can customize
    placeholders = Column(JSON, default=dict)  # Placeholder values

    # Visibility
    visibility = Column(String(20), default=TemplateVisibility.PRIVATE.value)
    shared_with = Column(JSON, default=list)  # Tenant IDs for shared

    # Tags and search
    tags = Column(JSON, default=list)
    icon = Column(String(100), nullable=True)
    color = Column(String(20), nullable=True)

    # Usage stats
    usage_count = Column(Integer, default=0)
    rating = Column(Integer, nullable=True)  # 1-5
    rating_count = Column(Integer, default=0)

    # Status
    published = Column(Boolean, default=False)
    featured = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_agent_templates_tenant_id", "tenant_id"),
        Index("idx_agent_templates_category", "category"),
        Index("idx_agent_templates_visibility", "visibility"),
        Index("idx_agent_templates_slug", "slug"),
        Index("idx_agent_templates_published", "published"),
    )


# Pydantic models
class ConfigurableField(BaseModel):
    """A field that can be customized when using template."""

    path: str  # JSON path in definition
    label: str
    description: str | None = None
    type: str = "string"  # string, number, boolean, select, multi-select
    required: bool = False
    default: Any = None
    options: list[dict[str, Any]] | None = None  # For select types
    validation: dict[str, Any] | None = None


class TemplateCreate(BaseModel):
    """Request to create a template."""

    name: str
    display_name: str
    description: str | None = None
    long_description: str | None = None
    category: TemplateCategory = TemplateCategory.CUSTOM
    definition: dict[str, Any]
    default_config: dict[str, Any] = Field(default_factory=dict)
    required_integrations: list[str] = Field(default_factory=list)
    required_permissions: list[str] = Field(default_factory=list)
    configurable_fields: list[ConfigurableField] = Field(default_factory=list)
    placeholders: dict[str, str] = Field(default_factory=dict)
    visibility: TemplateVisibility = TemplateVisibility.PRIVATE
    tags: list[str] = Field(default_factory=list)
    icon: str | None = None
    color: str | None = None


class TemplateUpdate(BaseModel):
    """Request to update a template."""

    display_name: str | None = None
    description: str | None = None
    long_description: str | None = None
    category: TemplateCategory | None = None
    definition: dict[str, Any] | None = None
    configurable_fields: list[ConfigurableField] | None = None
    visibility: TemplateVisibility | None = None
    tags: list[str] | None = None
    published: bool | None = None


class TemplateResponse(BaseModel):
    """Template response."""

    id: UUID
    name: str
    slug: str
    display_name: str
    description: str | None
    category: str
    version: str
    visibility: str
    tags: list[str]
    icon: str | None
    color: str | None
    usage_count: int
    rating: int | None
    published: bool
    featured: bool
    created_at: datetime
    required_integrations: list[str]


class TemplateDetail(TemplateResponse):
    """Detailed template response."""

    long_description: str | None
    definition: dict[str, Any]
    default_config: dict[str, Any]
    configurable_fields: list[dict[str, Any]]
    placeholders: dict[str, str]
    required_permissions: list[str]


class InstantiateTemplateRequest(BaseModel):
    """Request to create agent from template."""

    template_id: UUID | None = None
    template_slug: str | None = None
    agent_name: str
    configuration: dict[str, Any] = Field(default_factory=dict)
    deploy: bool = False
```

### Step 2: Template Repository

```python
# services/agent-service/src/aswa_agents/repositories/template_repository.py
"""Repository for agent templates."""

import re
from datetime import datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select, and_, or_, func, desc, update
from sqlalchemy.ext.asyncio import AsyncSession

from aswa_agents.db.session import get_session
from aswa_agents.models.template import (
    AgentTemplateModel,
    TemplateCategory,
    TemplateVisibility,
    TemplateCreate,
)

logger = structlog.get_logger()


class TemplateRepository:
    """Repository for managing agent templates."""

    def __init__(self, session: AsyncSession | None = None):
        self._session = session
        self._logger = logger.bind(component="TemplateRepository")

    async def _get_session(self) -> AsyncSession:
        if self._session:
            return self._session
        return await get_session()

    async def create(
        self,
        tenant_id: str | None,
        template: TemplateCreate,
        created_by: str,
    ) -> AgentTemplateModel:
        """Create a new template."""
        session = await self._get_session()

        # Generate slug
        slug = self._generate_slug(template.name)

        db_template = AgentTemplateModel(
            tenant_id=tenant_id,
            created_by=created_by,
            name=template.name,
            slug=slug,
            display_name=template.display_name,
            description=template.description,
            long_description=template.long_description,
            category=template.category.value,
            definition=template.definition,
            default_config=template.default_config,
            required_integrations=template.required_integrations,
            required_permissions=template.required_permissions,
            configurable_fields=[f.model_dump() for f in template.configurable_fields],
            placeholders=template.placeholders,
            visibility=template.visibility.value,
            tags=template.tags,
            icon=template.icon,
            color=template.color,
        )

        session.add(db_template)
        await session.commit()
        await session.refresh(db_template)

        self._logger.info(
            "Created template",
            template_id=str(db_template.id),
            name=template.name,
        )

        return db_template

    def _generate_slug(self, name: str) -> str:
        """Generate URL-friendly slug from name."""
        slug = name.lower()
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        slug = re.sub(r"-+", "-", slug)
        slug = slug.strip("-")
        return f"{slug}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    async def get_by_id(
        self,
        template_id: UUID,
        tenant_id: str | None = None,
    ) -> AgentTemplateModel | None:
        """Get template by ID."""
        session = await self._get_session()

        conditions = [AgentTemplateModel.id == template_id]

        # Access control
        if tenant_id:
            conditions.append(
                or_(
                    AgentTemplateModel.visibility == TemplateVisibility.PUBLIC.value,
                    AgentTemplateModel.tenant_id == tenant_id,
                    AgentTemplateModel.shared_with.contains([tenant_id]),
                )
            )

        result = await session.execute(
            select(AgentTemplateModel).where(and_(*conditions))
        )

        return result.scalar_one_or_none()

    async def get_by_slug(
        self,
        slug: str,
        tenant_id: str | None = None,
    ) -> AgentTemplateModel | None:
        """Get template by slug."""
        session = await self._get_session()

        conditions = [AgentTemplateModel.slug == slug]

        if tenant_id:
            conditions.append(
                or_(
                    AgentTemplateModel.visibility == TemplateVisibility.PUBLIC.value,
                    AgentTemplateModel.tenant_id == tenant_id,
                )
            )

        result = await session.execute(
            select(AgentTemplateModel).where(and_(*conditions))
        )

        return result.scalar_one_or_none()

    async def list_templates(
        self,
        tenant_id: str | None = None,
        category: TemplateCategory | None = None,
        tags: list[str] | None = None,
        search: str | None = None,
        featured_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AgentTemplateModel], int]:
        """List templates with filters."""
        session = await self._get_session()

        conditions = [AgentTemplateModel.published == True]

        # Access control
        if tenant_id:
            conditions.append(
                or_(
                    AgentTemplateModel.visibility == TemplateVisibility.PUBLIC.value,
                    AgentTemplateModel.tenant_id == tenant_id,
                    AgentTemplateModel.shared_with.contains([tenant_id]),
                )
            )
        else:
            conditions.append(
                AgentTemplateModel.visibility == TemplateVisibility.PUBLIC.value
            )

        if category:
            conditions.append(AgentTemplateModel.category == category.value)

        if featured_only:
            conditions.append(AgentTemplateModel.featured == True)

        if search:
            search_term = f"%{search}%"
            conditions.append(
                or_(
                    AgentTemplateModel.name.ilike(search_term),
                    AgentTemplateModel.display_name.ilike(search_term),
                    AgentTemplateModel.description.ilike(search_term),
                )
            )

        # Get total count
        count_result = await session.execute(
            select(func.count())
            .select_from(AgentTemplateModel)
            .where(and_(*conditions))
        )
        total = count_result.scalar()

        # Get templates
        result = await session.execute(
            select(AgentTemplateModel)
            .where(and_(*conditions))
            .order_by(
                desc(AgentTemplateModel.featured),
                desc(AgentTemplateModel.usage_count),
            )
            .limit(limit)
            .offset(offset)
        )

        return result.scalars().all(), total

    async def list_by_tenant(
        self,
        tenant_id: str,
        include_drafts: bool = True,
    ) -> list[AgentTemplateModel]:
        """List templates owned by a tenant."""
        session = await self._get_session()

        conditions = [AgentTemplateModel.tenant_id == tenant_id]

        if not include_drafts:
            conditions.append(AgentTemplateModel.published == True)

        result = await session.execute(
            select(AgentTemplateModel)
            .where(and_(*conditions))
            .order_by(desc(AgentTemplateModel.created_at))
        )

        return result.scalars().all()

    async def update(
        self,
        template_id: UUID,
        tenant_id: str,
        updates: dict[str, Any],
    ) -> AgentTemplateModel | None:
        """Update a template."""
        session = await self._get_session()

        result = await session.execute(
            select(AgentTemplateModel).where(
                and_(
                    AgentTemplateModel.id == template_id,
                    AgentTemplateModel.tenant_id == tenant_id,
                )
            )
        )
        template = result.scalar_one_or_none()

        if not template:
            return None

        for key, value in updates.items():
            if hasattr(template, key) and value is not None:
                setattr(template, key, value)

        template.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(template)

        return template

    async def delete(
        self,
        template_id: UUID,
        tenant_id: str,
    ) -> bool:
        """Delete a template."""
        session = await self._get_session()

        result = await session.execute(
            select(AgentTemplateModel).where(
                and_(
                    AgentTemplateModel.id == template_id,
                    AgentTemplateModel.tenant_id == tenant_id,
                )
            )
        )
        template = result.scalar_one_or_none()

        if not template:
            return False

        await session.delete(template)
        await session.commit()

        return True

    async def increment_usage(self, template_id: UUID) -> None:
        """Increment template usage count."""
        session = await self._get_session()

        await session.execute(
            update(AgentTemplateModel)
            .where(AgentTemplateModel.id == template_id)
            .values(usage_count=AgentTemplateModel.usage_count + 1)
        )
        await session.commit()

    async def rate_template(
        self,
        template_id: UUID,
        rating: int,
    ) -> None:
        """Add a rating to a template."""
        session = await self._get_session()

        result = await session.execute(
            select(AgentTemplateModel).where(AgentTemplateModel.id == template_id)
        )
        template = result.scalar_one_or_none()

        if not template:
            return

        # Calculate new average
        current_total = (template.rating or 0) * template.rating_count
        new_count = template.rating_count + 1
        new_rating = (current_total + rating) // new_count

        template.rating = new_rating
        template.rating_count = new_count

        await session.commit()
```

### Step 3: Template Service

```python
# services/agent-service/src/aswa_agents/services/template_service.py
"""Template service for agent template management."""

import copy
import re
from typing import Any
from uuid import UUID

import structlog

from aswa_agents.models.template import (
    TemplateCreate,
    TemplateUpdate,
    TemplateCategory,
    TemplateVisibility,
    InstantiateTemplateRequest,
    ConfigurableField,
)
from aswa_agents.repositories.template_repository import TemplateRepository
from aswa_agents.repositories.agent_repository import AgentRepository

logger = structlog.get_logger()


class TemplateService:
    """
    Service for managing agent templates.

    Provides template creation, instantiation, and management.
    """

    def __init__(self):
        self._repo = TemplateRepository()
        self._agent_repo = AgentRepository()
        self._logger = logger.bind(component="TemplateService")

    async def create_template(
        self,
        tenant_id: str,
        template: TemplateCreate,
        created_by: str,
    ) -> dict[str, Any]:
        """Create a new template."""
        # Validate definition
        self._validate_definition(template.definition)

        # Extract configurable fields if not provided
        if not template.configurable_fields:
            template.configurable_fields = self._extract_configurable_fields(
                template.definition
            )

        db_template = await self._repo.create(tenant_id, template, created_by)

        self._logger.info(
            "Template created",
            template_id=str(db_template.id),
            name=template.name,
        )

        return self._to_response(db_template)

    async def get_template(
        self,
        template_id: UUID | None = None,
        slug: str | None = None,
        tenant_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Get a template by ID or slug."""
        if template_id:
            template = await self._repo.get_by_id(template_id, tenant_id)
        elif slug:
            template = await self._repo.get_by_slug(slug, tenant_id)
        else:
            return None

        if not template:
            return None

        return self._to_detail_response(template)

    async def list_templates(
        self,
        tenant_id: str | None = None,
        category: TemplateCategory | None = None,
        search: str | None = None,
        featured_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List available templates."""
        templates, total = await self._repo.list_templates(
            tenant_id=tenant_id,
            category=category,
            search=search,
            featured_only=featured_only,
            limit=limit,
            offset=offset,
        )

        return {
            "templates": [self._to_response(t) for t in templates],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def list_by_category(
        self,
        tenant_id: str | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """List templates grouped by category."""
        result = {}

        for category in TemplateCategory:
            templates, _ = await self._repo.list_templates(
                tenant_id=tenant_id,
                category=category,
                limit=10,
            )
            if templates:
                result[category.value] = [self._to_response(t) for t in templates]

        return result

    async def update_template(
        self,
        template_id: UUID,
        tenant_id: str,
        update: TemplateUpdate,
    ) -> dict[str, Any] | None:
        """Update a template."""
        updates = update.model_dump(exclude_unset=True)

        # Convert enums to values
        if "category" in updates and updates["category"]:
            updates["category"] = updates["category"].value
        if "visibility" in updates and updates["visibility"]:
            updates["visibility"] = updates["visibility"].value

        template = await self._repo.update(template_id, tenant_id, updates)

        if not template:
            return None

        return self._to_detail_response(template)

    async def delete_template(
        self,
        template_id: UUID,
        tenant_id: str,
    ) -> bool:
        """Delete a template."""
        return await self._repo.delete(template_id, tenant_id)

    async def instantiate_template(
        self,
        tenant_id: str,
        request: InstantiateTemplateRequest,
        created_by: str,
    ) -> dict[str, Any]:
        """
        Create an agent from a template.

        Applies user configuration and creates a new agent.
        """
        # Get template
        template = None
        if request.template_id:
            template = await self._repo.get_by_id(request.template_id, tenant_id)
        elif request.template_slug:
            template = await self._repo.get_by_slug(request.template_slug, tenant_id)

        if not template:
            raise ValueError("Template not found")

        # Create agent definition from template
        definition = copy.deepcopy(template.definition)

        # Apply default config
        definition = self._apply_config(definition, template.default_config)

        # Apply user configuration
        definition = self._apply_config(definition, request.configuration)

        # Replace placeholders
        definition = self._replace_placeholders(
            definition,
            template.placeholders,
            request.configuration,
        )

        # Set agent name
        definition["name"] = request.agent_name
        definition["display_name"] = request.agent_name

        # Mark as created from template
        definition["template_id"] = str(template.id)
        definition["template_name"] = template.name

        # Create agent
        agent = await self._agent_repo.create(
            tenant_id=tenant_id,
            definition=definition,
            created_by=created_by,
        )

        # Increment template usage
        await self._repo.increment_usage(template.id)

        self._logger.info(
            "Agent created from template",
            agent_id=str(agent.id),
            template_id=str(template.id),
        )

        return {
            "agent_id": str(agent.id),
            "agent_name": request.agent_name,
            "template_id": str(template.id),
            "template_name": template.name,
        }

    async def create_template_from_agent(
        self,
        agent_id: UUID,
        tenant_id: str,
        name: str,
        description: str | None,
        created_by: str,
    ) -> dict[str, Any]:
        """Create a template from an existing agent."""
        agent = await self._agent_repo.get_by_id(str(agent_id))

        if not agent or agent.tenant_id != tenant_id:
            raise ValueError("Agent not found")

        # Create template from agent definition
        template = TemplateCreate(
            name=name,
            display_name=name,
            description=description,
            category=TemplateCategory.CUSTOM,
            definition=agent.definition,
            configurable_fields=self._extract_configurable_fields(agent.definition),
        )

        return await self.create_template(tenant_id, template, created_by)

    def _validate_definition(self, definition: dict[str, Any]) -> None:
        """Validate template definition."""
        required_fields = ["trigger", "actions"]
        for field in required_fields:
            if field not in definition:
                raise ValueError(f"Missing required field: {field}")

    def _extract_configurable_fields(
        self,
        definition: dict[str, Any],
    ) -> list[ConfigurableField]:
        """Extract commonly configurable fields from definition."""
        fields = []

        # Extract trigger configuration
        if "trigger" in definition:
            trigger = definition["trigger"]
            if "config" in trigger:
                for key in trigger["config"]:
                    fields.append(ConfigurableField(
                        path=f"trigger.config.{key}",
                        label=key.replace("_", " ").title(),
                        type="string",
                    ))

        # Extract action configurations
        for i, action in enumerate(definition.get("actions", [])):
            if "config" in action:
                for key in action["config"]:
                    fields.append(ConfigurableField(
                        path=f"actions.{i}.config.{key}",
                        label=f"{action.get('id', f'Action {i}')} - {key}",
                        type="string",
                    ))

        return fields

    def _apply_config(
        self,
        definition: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply configuration to definition."""
        result = copy.deepcopy(definition)

        for path, value in config.items():
            self._set_nested_value(result, path, value)

        return result

    def _set_nested_value(
        self,
        data: dict[str, Any],
        path: str,
        value: Any,
    ) -> None:
        """Set value at nested path."""
        parts = path.split(".")
        current = data

        for part in parts[:-1]:
            if part.isdigit():
                part = int(part)
            if isinstance(current, list) and isinstance(part, int):
                current = current[part]
            elif isinstance(current, dict):
                if part not in current:
                    current[part] = {}
                current = current[part]

        final_key = parts[-1]
        if final_key.isdigit():
            final_key = int(final_key)

        if isinstance(current, list) and isinstance(final_key, int):
            current[final_key] = value
        elif isinstance(current, dict):
            current[final_key] = value

    def _replace_placeholders(
        self,
        definition: dict[str, Any],
        placeholders: dict[str, str],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Replace placeholders in definition."""

        def replace_in_value(value: Any) -> Any:
            if isinstance(value, str):
                for placeholder, default in placeholders.items():
                    pattern = f"{{{{ {placeholder} }}}}"
                    replacement = config.get(placeholder, default)
                    value = value.replace(pattern, str(replacement))
                return value
            elif isinstance(value, dict):
                return {k: replace_in_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [replace_in_value(v) for v in value]
            return value

        return replace_in_value(definition)

    def _to_response(self, template) -> dict[str, Any]:
        """Convert template to response."""
        return {
            "id": str(template.id),
            "name": template.name,
            "slug": template.slug,
            "display_name": template.display_name,
            "description": template.description,
            "category": template.category,
            "version": template.version,
            "visibility": template.visibility,
            "tags": template.tags or [],
            "icon": template.icon,
            "color": template.color,
            "usage_count": template.usage_count,
            "rating": template.rating,
            "published": template.published,
            "featured": template.featured,
            "created_at": template.created_at.isoformat(),
            "required_integrations": template.required_integrations or [],
        }

    def _to_detail_response(self, template) -> dict[str, Any]:
        """Convert template to detailed response."""
        response = self._to_response(template)
        response.update({
            "long_description": template.long_description,
            "definition": template.definition,
            "default_config": template.default_config,
            "configurable_fields": template.configurable_fields or [],
            "placeholders": template.placeholders or {},
            "required_permissions": template.required_permissions or [],
        })
        return response
```

### Step 4: Built-in Templates

```python
# services/agent-service/src/aswa_agents/templates/builtin.py
"""Built-in agent templates."""

from aswa_agents.models.template import TemplateCreate, TemplateCategory, ConfigurableField

BUILTIN_TEMPLATES = [
    TemplateCreate(
        name="email-summarizer",
        display_name="Email Summarizer",
        description="Automatically summarize incoming emails and extract action items",
        long_description="""
This agent monitors your inbox for new emails and provides concise summaries
with extracted action items. Perfect for staying on top of high-volume email.

**Features:**
- Summarizes email content
- Extracts action items and deadlines
- Identifies key stakeholders
- Optional Slack notification
        """,
        category=TemplateCategory.PRODUCTIVITY,
        definition={
            "trigger": {
                "type": "email",
                "config": {"filter": "is:unread"},
            },
            "actions": [
                {
                    "id": "summarize",
                    "type": "summarize",
                    "config": {
                        "max_length": 200,
                        "style": "bullet_points",
                    },
                },
                {
                    "id": "extract_actions",
                    "type": "extract",
                    "config": {"extract_type": "action_items"},
                },
                {
                    "id": "notify",
                    "type": "send_slack",
                    "config": {
                        "channel": "{{ slack_channel }}",
                        "template": "email_summary",
                    },
                },
            ],
        },
        configurable_fields=[
            ConfigurableField(
                path="trigger.config.filter",
                label="Email Filter",
                description="Filter for which emails to process",
                type="string",
                default="is:unread",
            ),
            ConfigurableField(
                path="actions.0.config.max_length",
                label="Summary Length",
                description="Maximum length of summary",
                type="number",
                default=200,
            ),
        ],
        placeholders={"slack_channel": "#email-summaries"},
        required_integrations=["email", "slack"],
        required_permissions=["action:summarize", "action:extract", "action:send_slack"],
        tags=["email", "productivity", "summarization"],
        icon="mail",
        color="#3B82F6",
    ),
    TemplateCreate(
        name="support-ticket-router",
        display_name="Support Ticket Router",
        description="Automatically categorize and route support tickets to the right team",
        category=TemplateCategory.SUPPORT,
        definition={
            "trigger": {
                "type": "ticket",
                "config": {"source": "zendesk"},
            },
            "actions": [
                {
                    "id": "analyze",
                    "type": "extract",
                    "config": {
                        "extract_type": "entities",
                        "entity_types": ["product", "issue_type", "sentiment"],
                    },
                },
                {
                    "id": "categorize",
                    "type": "condition",
                    "config": {
                        "rules": [
                            {
                                "field": "outputs.analyze.sentiment",
                                "operator": "equals",
                                "value": "negative",
                            },
                        ],
                        "true_branch": "escalate",
                        "false_branch": "route_normal",
                    },
                },
                {
                    "id": "route_normal",
                    "type": "create_ticket",
                    "config": {
                        "provider": "jira",
                        "project": "{{ jira_project }}",
                        "assign_to": "{{ default_assignee }}",
                    },
                },
            ],
        },
        configurable_fields=[
            ConfigurableField(
                path="trigger.config.source",
                label="Ticket Source",
                type="select",
                options=[
                    {"value": "zendesk", "label": "Zendesk"},
                    {"value": "freshdesk", "label": "Freshdesk"},
                    {"value": "email", "label": "Email"},
                ],
            ),
        ],
        placeholders={
            "jira_project": "SUPPORT",
            "default_assignee": "support-team",
        },
        required_integrations=["zendesk", "jira"],
        tags=["support", "tickets", "automation"],
        icon="headphones",
        color="#10B981",
    ),
    TemplateCreate(
        name="meeting-notes-processor",
        display_name="Meeting Notes Processor",
        description="Extract and organize key points from meeting notes and transcripts",
        category=TemplateCategory.PRODUCTIVITY,
        definition={
            "trigger": {
                "type": "document",
                "config": {"pattern": "meeting*.txt"},
            },
            "actions": [
                {
                    "id": "summarize_meeting",
                    "type": "summarize",
                    "config": {
                        "max_length": 500,
                        "style": "meeting_summary",
                    },
                },
                {
                    "id": "extract_decisions",
                    "type": "extract",
                    "config": {"extract_type": "decisions"},
                },
                {
                    "id": "extract_actions",
                    "type": "extract",
                    "config": {"extract_type": "action_items"},
                },
                {
                    "id": "create_tasks",
                    "type": "loop",
                    "config": {
                        "items_field": "outputs.extract_actions.items",
                        "actions": ["create_ticket_for_action"],
                    },
                },
            ],
        },
        placeholders={},
        required_integrations=["documents"],
        tags=["meetings", "productivity", "notes"],
        icon="calendar",
        color="#8B5CF6",
    ),
    TemplateCreate(
        name="slack-qa-bot",
        display_name="Slack Q&A Bot",
        description="Answer questions in Slack using your knowledge base",
        category=TemplateCategory.COMMUNICATION,
        definition={
            "trigger": {
                "type": "slack",
                "config": {
                    "event": "app_mention",
                    "channels": ["{{ monitored_channels }}"],
                },
            },
            "actions": [
                {
                    "id": "search_knowledge",
                    "type": "query_knowledge",
                    "config": {
                        "query_field": "trigger.text",
                        "top_k": 5,
                    },
                },
                {
                    "id": "generate_response",
                    "type": "summarize",
                    "config": {
                        "context": "outputs.search_knowledge.results",
                        "style": "qa_response",
                    },
                },
                {
                    "id": "respond",
                    "type": "send_slack",
                    "config": {
                        "reply_to_thread": True,
                        "content_field": "outputs.generate_response.summary",
                    },
                },
            ],
        },
        placeholders={"monitored_channels": "#general"},
        required_integrations=["slack", "knowledge_base"],
        tags=["slack", "qa", "knowledge"],
        icon="message-circle",
        color="#E11D48",
    ),
]


async def seed_builtin_templates(tenant_id: str | None = None) -> None:
    """Seed the database with built-in templates."""
    from aswa_agents.repositories.template_repository import TemplateRepository

    repo = TemplateRepository()

    for template in BUILTIN_TEMPLATES:
        # Check if already exists
        existing = await repo.get_by_slug(template.name.replace("_", "-"), tenant_id)
        if existing:
            continue

        # Create with public visibility
        template.visibility = TemplateVisibility.PUBLIC

        await repo.create(
            tenant_id=None,  # Public templates have no tenant
            template=template,
            created_by="system",
        )
```

### Step 5: Template API Endpoints

```python
# services/agent-service/src/aswa_agents/api/templates.py
"""API endpoints for agent templates."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aswa_agents.models.template import (
    TemplateCreate,
    TemplateUpdate,
    TemplateCategory,
    InstantiateTemplateRequest,
)
from aswa_agents.services.template_service import TemplateService

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("")
async def list_templates(
    category: TemplateCategory | None = None,
    search: str | None = None,
    featured: bool = False,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List available templates."""
    tenant_id = "default-tenant"

    service = TemplateService()
    return await service.list_templates(
        tenant_id=tenant_id,
        category=category,
        search=search,
        featured_only=featured,
        limit=limit,
        offset=offset,
    )


@router.get("/categories")
async def list_by_category() -> dict[str, Any]:
    """List templates grouped by category."""
    tenant_id = "default-tenant"

    service = TemplateService()
    return await service.list_by_category(tenant_id)


@router.get("/mine")
async def list_my_templates(
    include_drafts: bool = True,
) -> dict[str, Any]:
    """List templates created by current tenant."""
    tenant_id = "default-tenant"

    from aswa_agents.repositories.template_repository import TemplateRepository
    repo = TemplateRepository()
    templates = await repo.list_by_tenant(tenant_id, include_drafts)

    service = TemplateService()
    return {
        "templates": [service._to_response(t) for t in templates],
        "total": len(templates),
    }


@router.get("/{template_id}")
async def get_template(template_id: UUID) -> dict[str, Any]:
    """Get template details."""
    tenant_id = "default-tenant"

    service = TemplateService()
    template = await service.get_template(template_id=template_id, tenant_id=tenant_id)

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return template


@router.get("/slug/{slug}")
async def get_template_by_slug(slug: str) -> dict[str, Any]:
    """Get template by slug."""
    tenant_id = "default-tenant"

    service = TemplateService()
    template = await service.get_template(slug=slug, tenant_id=tenant_id)

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return template


@router.post("")
async def create_template(template: TemplateCreate) -> dict[str, Any]:
    """Create a new template."""
    tenant_id = "default-tenant"
    user_id = "current-user"

    service = TemplateService()
    return await service.create_template(tenant_id, template, user_id)


@router.put("/{template_id}")
async def update_template(
    template_id: UUID,
    update: TemplateUpdate,
) -> dict[str, Any]:
    """Update a template."""
    tenant_id = "default-tenant"

    service = TemplateService()
    result = await service.update_template(template_id, tenant_id, update)

    if not result:
        raise HTTPException(status_code=404, detail="Template not found")

    return result


@router.delete("/{template_id}")
async def delete_template(template_id: UUID) -> dict[str, Any]:
    """Delete a template."""
    tenant_id = "default-tenant"

    service = TemplateService()
    success = await service.delete_template(template_id, tenant_id)

    if not success:
        raise HTTPException(status_code=404, detail="Template not found")

    return {"deleted": True}


@router.post("/instantiate")
async def instantiate_template(
    request: InstantiateTemplateRequest,
) -> dict[str, Any]:
    """Create an agent from a template."""
    tenant_id = "default-tenant"
    user_id = "current-user"

    service = TemplateService()
    try:
        return await service.instantiate_template(tenant_id, request, user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/from-agent/{agent_id}")
async def create_from_agent(
    agent_id: UUID,
    name: str = Query(...),
    description: str | None = None,
) -> dict[str, Any]:
    """Create a template from an existing agent."""
    tenant_id = "default-tenant"
    user_id = "current-user"

    service = TemplateService()
    try:
        return await service.create_template_from_agent(
            agent_id, tenant_id, name, description, user_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{template_id}/rate")
async def rate_template(
    template_id: UUID,
    rating: int = Query(..., ge=1, le=5),
) -> dict[str, Any]:
    """Rate a template."""
    from aswa_agents.repositories.template_repository import TemplateRepository

    repo = TemplateRepository()
    await repo.rate_template(template_id, rating)

    return {"rated": True, "rating": rating}
```

## Test Cases

```python
# services/agent-service/tests/unit/test_templates.py
"""Tests for agent templates."""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, patch

from aswa_agents.models.template import (
    TemplateCreate,
    TemplateCategory,
    TemplateVisibility,
    InstantiateTemplateRequest,
    ConfigurableField,
)
from aswa_agents.services.template_service import TemplateService
from aswa_agents.repositories.template_repository import TemplateRepository


class TestTemplateRepository:
    """Test TemplateRepository."""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_create_template(self, mock_session):
        """Test creating a template."""
        repo = TemplateRepository(session=mock_session)

        template = TemplateCreate(
            name="test-template",
            display_name="Test Template",
            description="A test template",
            category=TemplateCategory.PRODUCTIVITY,
            definition={
                "trigger": {"type": "email"},
                "actions": [],
            },
        )

        await repo.create("test-tenant", template, "user@example.com")

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called()


class TestTemplateService:
    """Test TemplateService."""

    @pytest.fixture
    def service(self):
        return TemplateService()

    @pytest.mark.asyncio
    async def test_create_template(self, service):
        """Test creating a template."""
        with patch.object(service._repo, "create") as mock_create:
            mock_template = AsyncMock()
            mock_template.id = uuid4()
            mock_template.name = "test"
            mock_template.slug = "test-123"
            mock_template.display_name = "Test"
            mock_template.description = "Test"
            mock_template.category = "productivity"
            mock_template.version = "1.0.0"
            mock_template.visibility = "private"
            mock_template.tags = []
            mock_template.icon = None
            mock_template.color = None
            mock_template.usage_count = 0
            mock_template.rating = None
            mock_template.published = False
            mock_template.featured = False
            mock_template.created_at = AsyncMock()
            mock_template.required_integrations = []
            mock_create.return_value = mock_template

            template = TemplateCreate(
                name="test",
                display_name="Test",
                description="Test",
                category=TemplateCategory.PRODUCTIVITY,
                definition={
                    "trigger": {"type": "email"},
                    "actions": [],
                },
            )

            result = await service.create_template(
                "test-tenant", template, "user@example.com"
            )

            assert result["name"] == "test"
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_instantiate_template(self, service):
        """Test instantiating a template."""
        mock_template = AsyncMock()
        mock_template.id = uuid4()
        mock_template.name = "email-summarizer"
        mock_template.definition = {
            "trigger": {"type": "email"},
            "actions": [
                {"id": "summarize", "type": "summarize", "config": {}},
            ],
        }
        mock_template.default_config = {}
        mock_template.placeholders = {}

        mock_agent = AsyncMock()
        mock_agent.id = uuid4()

        with patch.object(service._repo, "get_by_id") as mock_get:
            mock_get.return_value = mock_template

            with patch.object(service._repo, "increment_usage"):
                with patch.object(service._agent_repo, "create") as mock_create:
                    mock_create.return_value = mock_agent

                    request = InstantiateTemplateRequest(
                        template_id=mock_template.id,
                        agent_name="My Email Agent",
                    )

                    result = await service.instantiate_template(
                        "test-tenant", request, "user@example.com"
                    )

                    assert result["agent_name"] == "My Email Agent"
                    assert result["template_id"] == str(mock_template.id)

    def test_apply_config(self, service):
        """Test applying configuration."""
        definition = {
            "trigger": {"type": "email", "config": {"filter": ""}},
            "actions": [
                {"id": "a1", "type": "summarize", "config": {"max_length": 100}},
            ],
        }

        config = {
            "trigger.config.filter": "is:important",
            "actions.0.config.max_length": 200,
        }

        result = service._apply_config(definition, config)

        assert result["trigger"]["config"]["filter"] == "is:important"
        assert result["actions"][0]["config"]["max_length"] == 200

    def test_replace_placeholders(self, service):
        """Test placeholder replacement."""
        definition = {
            "actions": [
                {"config": {"channel": "{{ slack_channel }}"}},
            ],
        }

        placeholders = {"slack_channel": "#default"}
        config = {"slack_channel": "#custom"}

        result = service._replace_placeholders(definition, placeholders, config)

        assert result["actions"][0]["config"]["channel"] == "#custom"

    def test_extract_configurable_fields(self, service):
        """Test extracting configurable fields."""
        definition = {
            "trigger": {"type": "email", "config": {"filter": "is:unread"}},
            "actions": [
                {
                    "id": "summarize",
                    "type": "summarize",
                    "config": {"max_length": 200},
                },
            ],
        }

        fields = service._extract_configurable_fields(definition)

        assert len(fields) >= 2
        paths = [f.path for f in fields]
        assert "trigger.config.filter" in paths


class TestBuiltinTemplates:
    """Test built-in templates."""

    def test_builtin_templates_valid(self):
        """Test that all built-in templates are valid."""
        from aswa_agents.templates.builtin import BUILTIN_TEMPLATES

        for template in BUILTIN_TEMPLATES:
            assert template.name
            assert template.display_name
            assert template.definition
            assert "trigger" in template.definition
            assert "actions" in template.definition
```

## Verification Steps

1. **Run unit tests:**
   ```bash
   cd services/agent-service
   pytest tests/unit/test_templates.py -v
   ```

2. **Seed built-in templates:**
   ```python
   from aswa_agents.templates.builtin import seed_builtin_templates

   await seed_builtin_templates()
   ```

3. **Test API endpoints:**
   ```bash
   # List templates
   curl http://localhost:8000/api/v1/templates

   # Get template by ID
   curl http://localhost:8000/api/v1/templates/{id}

   # Create from template
   curl -X POST http://localhost:8000/api/v1/templates/instantiate \
     -H "Content-Type: application/json" \
     -d '{
       "template_slug": "email-summarizer",
       "agent_name": "My Email Agent",
       "configuration": {
         "trigger.config.filter": "is:important"
       }
     }'
   ```

## Next Task

Proceed to `task-9.7.2-template-library-ui.md` for implementing the template library UI.
