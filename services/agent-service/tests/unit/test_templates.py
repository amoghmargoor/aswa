"""Tests for agent templates library and engine."""

from uuid import uuid4

import pytest

from aswa_agents.templates import (
    AgentTemplate,
    BUILTIN_TEMPLATES,
    TemplateCategory,
    TemplateEngine,
    TemplateLibrary,
    TemplateVariable,
    TemplateVisibility,
)


class TestTemplateLibrary:
    """Tests for TemplateLibrary class."""

    @pytest.fixture
    def tenant_id(self):
        """Create a tenant ID for testing."""
        return uuid4()

    @pytest.fixture
    def library(self, tenant_id):
        """Create a template library instance."""
        return TemplateLibrary(tenant_id)

    @pytest.fixture
    def sample_template(self):
        """Create a sample template."""
        return AgentTemplate(
            name="test-template",
            display_name="Test Template",
            description="A test template",
            category=TemplateCategory.CUSTOM,
            visibility=TemplateVisibility.PUBLIC,
            icon="test",
            tags=["test", "sample"],
            definition={
                "trigger": {"type": "manual"},
                "actions": [
                    {"id": "action1", "type": "log", "config": {"message": "{{message}}"}}
                ],
            },
            variables=[
                TemplateVariable(
                    name="message",
                    display_name="Message",
                    description="The message to log",
                    type="string",
                    required=True,
                    default="Hello",
                )
            ],
        )

    def test_builtin_templates_loaded(self, library):
        """Test that builtin templates are loaded."""
        assert len(BUILTIN_TEMPLATES) > 0

    @pytest.mark.asyncio
    async def test_get_templates(self, library):
        """Test getting all templates."""
        templates = await library.get_templates()

        assert len(templates) >= len(BUILTIN_TEMPLATES)

    @pytest.mark.asyncio
    async def test_get_templates_by_category(self, library):
        """Test filtering templates by category."""
        templates = await library.get_templates(category=TemplateCategory.COMMUNICATION)

        assert all(t.category == TemplateCategory.COMMUNICATION for t in templates)

    @pytest.mark.asyncio
    async def test_get_templates_by_search(self, library):
        """Test searching templates."""
        templates = await library.get_templates(search="email")

        assert all(
            "email" in t.name.lower()
            or "email" in t.display_name.lower()
            or "email" in t.description.lower()
            for t in templates
        )

    @pytest.mark.asyncio
    async def test_get_templates_by_tags(self, library):
        """Test filtering templates by tags."""
        templates = await library.get_templates(tags=["slack"])

        assert all(any(tag in t.tags for tag in ["slack"]) for t in templates)

    @pytest.mark.asyncio
    async def test_get_template(self, library):
        """Test getting a specific template."""
        templates = await library.get_templates()
        template_id = templates[0].id

        template = await library.get_template(template_id)

        assert template is not None
        assert template.id == template_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_template(self, library):
        """Test getting a template that doesn't exist."""
        template = await library.get_template(uuid4())

        assert template is None

    @pytest.mark.asyncio
    async def test_create_template(self, library, sample_template):
        """Test creating a new template."""
        user_id = uuid4()

        created = await library.create_template(sample_template, user_id)

        assert created.name == "test-template"
        assert created.created_by == user_id
        assert created.owner_tenant_id == library.tenant_id

    @pytest.mark.asyncio
    async def test_update_template(self, library, sample_template, tenant_id):
        """Test updating a template."""
        user_id = uuid4()
        created = await library.create_template(sample_template, user_id)

        updated = await library.update_template(
            created.id,
            {"display_name": "Updated Template", "description": "Updated description"},
        )

        assert updated.display_name == "Updated Template"
        assert updated.description == "Updated description"

    @pytest.mark.asyncio
    async def test_update_template_not_found(self, library):
        """Test updating a template that doesn't exist."""
        with pytest.raises(ValueError, match="not found"):
            await library.update_template(uuid4(), {"name": "new-name"})

    @pytest.mark.asyncio
    async def test_delete_template(self, library, sample_template):
        """Test deleting a template."""
        user_id = uuid4()
        created = await library.create_template(sample_template, user_id)

        await library.delete_template(created.id)

        template = await library.get_template(created.id)
        assert template is None

    @pytest.mark.asyncio
    async def test_delete_template_not_found(self, library):
        """Test deleting a template that doesn't exist."""
        with pytest.raises(ValueError, match="not found"):
            await library.delete_template(uuid4())


class TestTemplateEngine:
    """Tests for TemplateEngine class."""

    @pytest.fixture
    def engine(self):
        """Create a template engine instance."""
        return TemplateEngine()

    @pytest.fixture
    def template_with_variables(self):
        """Create a template with variables."""
        return AgentTemplate(
            name="test-template",
            display_name="Test Template",
            description="A test template",
            category=TemplateCategory.CUSTOM,
            definition={
                "trigger": {
                    "type": "schedule",
                    "config": {"time": "{{schedule_time}}"},
                },
                "actions": [
                    {
                        "id": "notify",
                        "type": "send_email",
                        "config": {
                            "to": "{{recipient_email}}",
                            "subject": "{{email_subject}}",
                        },
                    }
                ],
            },
            variables=[
                TemplateVariable(
                    name="schedule_time",
                    display_name="Schedule Time",
                    type="string",
                    required=True,
                    default="09:00",
                ),
                TemplateVariable(
                    name="recipient_email",
                    display_name="Recipient Email",
                    type="string",
                    required=True,
                ),
                TemplateVariable(
                    name="email_subject",
                    display_name="Email Subject",
                    type="string",
                    required=False,
                    default="Notification",
                ),
            ],
        )

    def test_render_with_all_values(self, engine, template_with_variables):
        """Test rendering template with all values provided."""
        values = {
            "schedule_time": "14:00",
            "recipient_email": "user@example.com",
            "email_subject": "Alert",
        }

        result = engine.render(template_with_variables, values)

        assert result["trigger"]["config"]["time"] == "14:00"
        assert result["actions"][0]["config"]["to"] == "user@example.com"
        assert result["actions"][0]["config"]["subject"] == "Alert"

    def test_render_with_defaults(self, engine, template_with_variables):
        """Test rendering template with default values."""
        values = {
            "recipient_email": "user@example.com",
        }

        result = engine.render(template_with_variables, values)

        assert result["trigger"]["config"]["time"] == "09:00"  # default
        assert result["actions"][0]["config"]["subject"] == "Notification"  # default

    def test_render_missing_required(self, engine, template_with_variables):
        """Test rendering with missing required variables."""
        values = {
            "schedule_time": "10:00",
            # missing recipient_email which is required
        }

        with pytest.raises(ValueError, match="Missing required variable"):
            engine.render(template_with_variables, values)

    def test_validate_variables_valid(self, engine, template_with_variables):
        """Test validating valid variables."""
        values = {
            "schedule_time": "12:00",
            "recipient_email": "test@example.com",
        }

        errors = engine.validate_variables(template_with_variables, values)

        assert len(errors) == 0

    def test_validate_variables_missing_required(self, engine, template_with_variables):
        """Test validating with missing required variable."""
        values = {
            "schedule_time": "12:00",
        }

        errors = engine.validate_variables(template_with_variables, values)

        assert any("recipient_email" in e for e in errors)

    def test_validate_variables_wrong_type(self, engine):
        """Test validating with wrong variable type."""
        template = AgentTemplate(
            name="test",
            display_name="Test",
            description="Test",
            category=TemplateCategory.CUSTOM,
            definition={},
            variables=[
                TemplateVariable(
                    name="count",
                    display_name="Count",
                    type="number",
                    required=True,
                )
            ],
        )

        errors = engine.validate_variables(template, {"count": "not-a-number"})

        assert any("number" in e for e in errors)

    def test_validate_select_option(self, engine):
        """Test validating select option."""
        template = AgentTemplate(
            name="test",
            display_name="Test",
            description="Test",
            category=TemplateCategory.CUSTOM,
            definition={},
            variables=[
                TemplateVariable(
                    name="style",
                    display_name="Style",
                    type="select",
                    options=["brief", "detailed"],
                    required=True,
                )
            ],
        )

        # Valid option
        errors = engine.validate_variables(template, {"style": "brief"})
        assert len(errors) == 0

        # Invalid option
        errors = engine.validate_variables(template, {"style": "invalid"})
        assert len(errors) > 0

    def test_preview_with_placeholders(self, engine, template_with_variables):
        """Test preview with placeholder values."""
        preview = engine.preview(template_with_variables)

        assert "[Schedule Time]" in preview["trigger"]["config"]["time"]
        assert "[Recipient Email]" in preview["actions"][0]["config"]["to"]

    def test_preview_with_partial_values(self, engine, template_with_variables):
        """Test preview with some values provided."""
        values = {"recipient_email": "user@example.com"}

        preview = engine.preview(template_with_variables, values)

        assert preview["actions"][0]["config"]["to"] == "user@example.com"
        assert "[Schedule Time]" in preview["trigger"]["config"]["time"]

    def test_render_nested_path(self, engine):
        """Test rendering with nested variable paths."""
        template = AgentTemplate(
            name="test",
            display_name="Test",
            description="Test",
            category=TemplateCategory.CUSTOM,
            definition={
                "message": "Risk: {{risk.title}} - Severity: {{risk.severity}}",
            },
            variables=[],
        )

        values = {
            "risk": {"title": "Data Breach", "severity": "high"},
        }

        result = engine.render(template, values)

        assert result["message"] == "Risk: Data Breach - Severity: high"
