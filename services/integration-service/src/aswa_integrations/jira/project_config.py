from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, DateTime, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID
import uuid
import structlog

from aswa_integrations.models.integration import Base

logger = structlog.get_logger()


class JiraProjectConfigDB(Base):
    """Database model for Jira project configuration."""

    __tablename__ = "jira_project_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, nullable=False, index=True)
    project_key = Column(String, nullable=False)
    project_name = Column(String, nullable=False)

    # Issue type mappings
    risk_issue_type = Column(String, default="Bug")
    opportunity_issue_type = Column(String, default="Story")
    default_issue_type = Column(String, default="Task")

    # Priority mappings (severity to Jira priority)
    priority_mapping = Column(JSON, default={
        "critical": "Highest",
        "high": "High",
        "medium": "Medium",
        "low": "Low",
    })

    # Label configuration
    auto_labels = Column(JSON, default=["aswa", "ai-generated"])
    include_severity_label = Column(Boolean, default=True)
    include_type_label = Column(Boolean, default=True)

    # Custom fields
    custom_field_mappings = Column(JSON, default={})

    # Sync settings
    sync_enabled = Column(Boolean, default=True)
    sync_comments = Column(Boolean, default=True)
    sync_status = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class JiraProjectConfigCreate(BaseModel):
    """Schema for creating project configuration."""

    project_key: str = Field(..., min_length=1, max_length=10)
    project_name: str
    risk_issue_type: str = "Bug"
    opportunity_issue_type: str = "Story"
    default_issue_type: str = "Task"
    priority_mapping: dict[str, str] = Field(default_factory=lambda: {
        "critical": "Highest",
        "high": "High",
        "medium": "Medium",
        "low": "Low",
    })
    auto_labels: list[str] = Field(default_factory=lambda: ["aswa", "ai-generated"])
    include_severity_label: bool = True
    include_type_label: bool = True
    custom_field_mappings: dict[str, str] = Field(default_factory=dict)
    sync_enabled: bool = True
    sync_comments: bool = True
    sync_status: bool = True


class JiraProjectConfigUpdate(BaseModel):
    """Schema for updating project configuration."""

    risk_issue_type: str | None = None
    opportunity_issue_type: str | None = None
    default_issue_type: str | None = None
    priority_mapping: dict[str, str] | None = None
    auto_labels: list[str] | None = None
    include_severity_label: bool | None = None
    include_type_label: bool | None = None
    custom_field_mappings: dict[str, str] | None = None
    sync_enabled: bool | None = None
    sync_comments: bool | None = None
    sync_status: bool | None = None


class JiraProjectConfigResponse(BaseModel):
    """Schema for project configuration response."""

    id: str
    tenant_id: str
    project_key: str
    project_name: str
    risk_issue_type: str
    opportunity_issue_type: str
    default_issue_type: str
    priority_mapping: dict[str, str]
    auto_labels: list[str]
    include_severity_label: bool
    include_type_label: bool
    custom_field_mappings: dict[str, str]
    sync_enabled: bool
    sync_comments: bool
    sync_status: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JiraProjectConfig:
    """Manages Jira project configurations."""

    def __init__(self, session_factory):
        """Initialize project config manager.

        Args:
            session_factory: Database session factory
        """
        self.session_factory = session_factory

    async def create_config(
        self,
        tenant_id: str,
        data: JiraProjectConfigCreate,
    ) -> JiraProjectConfigResponse:
        """Create a project configuration.

        Args:
            tenant_id: ASWA tenant identifier
            data: Configuration data

        Returns:
            Created configuration
        """
        config = JiraProjectConfigDB(
            tenant_id=tenant_id,
            project_key=data.project_key,
            project_name=data.project_name,
            risk_issue_type=data.risk_issue_type,
            opportunity_issue_type=data.opportunity_issue_type,
            default_issue_type=data.default_issue_type,
            priority_mapping=data.priority_mapping,
            auto_labels=data.auto_labels,
            include_severity_label=data.include_severity_label,
            include_type_label=data.include_type_label,
            custom_field_mappings=data.custom_field_mappings,
            sync_enabled=data.sync_enabled,
            sync_comments=data.sync_comments,
            sync_status=data.sync_status,
        )

        async with self.session_factory() as session:
            session.add(config)
            await session.commit()
            await session.refresh(config)

        logger.info(
            "Jira project config created",
            tenant_id=tenant_id,
            project_key=data.project_key,
        )

        return JiraProjectConfigResponse.model_validate(config)

    async def get_config(
        self,
        tenant_id: str,
        project_key: str,
    ) -> JiraProjectConfigResponse | None:
        """Get configuration for a project.

        Args:
            tenant_id: ASWA tenant identifier
            project_key: Jira project key

        Returns:
            Configuration or None
        """
        from sqlalchemy import select

        async with self.session_factory() as session:
            result = await session.execute(
                select(JiraProjectConfigDB).where(
                    JiraProjectConfigDB.tenant_id == tenant_id,
                    JiraProjectConfigDB.project_key == project_key,
                )
            )
            config = result.scalar_one_or_none()

            if config:
                return JiraProjectConfigResponse.model_validate(config)
            return None

    async def update_config(
        self,
        tenant_id: str,
        project_key: str,
        data: JiraProjectConfigUpdate,
    ) -> JiraProjectConfigResponse | None:
        """Update project configuration.

        Args:
            tenant_id: ASWA tenant identifier
            project_key: Jira project key
            data: Update data

        Returns:
            Updated configuration or None
        """
        from sqlalchemy import select

        async with self.session_factory() as session:
            result = await session.execute(
                select(JiraProjectConfigDB).where(
                    JiraProjectConfigDB.tenant_id == tenant_id,
                    JiraProjectConfigDB.project_key == project_key,
                )
            )
            config = result.scalar_one_or_none()

            if not config:
                return None

            for field, value in data.model_dump(exclude_unset=True).items():
                setattr(config, field, value)

            config.updated_at = datetime.utcnow()

            await session.commit()
            await session.refresh(config)

            return JiraProjectConfigResponse.model_validate(config)

    async def delete_config(
        self,
        tenant_id: str,
        project_key: str,
    ) -> bool:
        """Delete project configuration.

        Args:
            tenant_id: ASWA tenant identifier
            project_key: Jira project key

        Returns:
            True if deleted
        """
        from sqlalchemy import select, delete

        async with self.session_factory() as session:
            result = await session.execute(
                select(JiraProjectConfigDB).where(
                    JiraProjectConfigDB.tenant_id == tenant_id,
                    JiraProjectConfigDB.project_key == project_key,
                )
            )
            config = result.scalar_one_or_none()

            if not config:
                return False

            await session.execute(
                delete(JiraProjectConfigDB).where(
                    JiraProjectConfigDB.id == config.id
                )
            )
            await session.commit()

            return True
