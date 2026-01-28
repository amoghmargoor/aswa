# Task 6.2.2: Jira Integration - Issue Creation

## Context

You are working on the ASWA integration service at `/services/integration-service/`. Jira connection is complete (Task 6.2.1). Now we need to implement issue creation and management.

## Objective

Create Jira issue management that:
1. Creates issues from ASWA insights
2. Updates existing issues
3. Manages issue attachments
4. Handles comments and transitions
5. Tracks issue-insight relationships

## Requirements

### 1. Create `/services/integration-service/src/aswa_integrations/jira/issue_manager.py`
```python
import uuid
from datetime import datetime
from typing import Any
import httpx
from sqlalchemy import Column, String, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import structlog

from aswa_integrations.models.integration import Base
from aswa_integrations.jira.oauth import JiraOAuthHandler
from aswa_integrations.jira.project_config import JiraProjectConfig, JiraProjectConfigResponse
from aswa_integrations.jira.field_mapper import JiraFieldMapper

logger = structlog.get_logger()


class JiraIssueLinkDB(Base):
    """Database model for tracking Jira issue links."""

    __tablename__ = "jira_issue_links"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, nullable=False, index=True)
    insight_id = Column(String, nullable=False, index=True)
    jira_issue_id = Column(String, nullable=False)
    jira_issue_key = Column(String, nullable=False)
    project_key = Column(String, nullable=False)
    issue_status = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_synced_at = Column(DateTime, nullable=True)
    sync_metadata = Column(JSON, default={})


class JiraIssueCreate(BaseModel):
    """Schema for creating a Jira issue."""
    insight_id: str
    project_key: str
    summary: str | None = None  # Override auto-generated
    description: str | None = None  # Override auto-generated
    issue_type: str | None = None  # Override from config
    priority: str | None = None  # Override from config
    labels: list[str] | None = None  # Additional labels
    assignee_id: str | None = None
    custom_fields: dict[str, Any] | None = None


class JiraIssueResponse(BaseModel):
    """Schema for Jira issue response."""
    id: str
    key: str
    self_url: str
    summary: str
    status: str
    priority: str | None
    assignee: str | None
    created: datetime
    updated: datetime
    insight_id: str | None = None


class JiraIssueManager:
    """Manages Jira issue creation and updates."""

    API_BASE = "https://api.atlassian.com/ex/jira"

    def __init__(
        self,
        oauth_handler: JiraOAuthHandler,
        session_factory,
    ):
        """Initialize issue manager.

        Args:
            oauth_handler: OAuth handler
            session_factory: Database session factory
        """
        self.oauth_handler = oauth_handler
        self.session_factory = session_factory
        self.project_config = JiraProjectConfig(session_factory)

    async def create_issue_from_insight(
        self,
        tenant_id: str,
        insight: dict[str, Any],
        project_key: str,
        overrides: JiraIssueCreate | None = None,
    ) -> JiraIssueResponse:
        """Create a Jira issue from an ASWA insight.

        Args:
            tenant_id: ASWA tenant identifier
            insight: ASWA insight data
            project_key: Target Jira project key
            overrides: Optional field overrides

        Returns:
            Created issue details
        """
        # Get OAuth tokens
        tokens = await self.oauth_handler.get_valid_tokens(tenant_id)
        if not tokens or not tokens.cloud_id:
            raise ValueError("Jira not connected")

        # Get project configuration
        config = await self.project_config.get_config(tenant_id, project_key)
        if not config:
            raise ValueError(f"Project {project_key} not configured")

        # Map insight to issue fields
        mapper = JiraFieldMapper(config)
        mapped = mapper.map_insight_to_issue(insight)

        # Apply overrides
        if overrides:
            if overrides.summary:
                mapped.summary = overrides.summary
            if overrides.description:
                mapped.description = overrides.description
            if overrides.issue_type:
                mapped.issue_type = overrides.issue_type
            if overrides.priority:
                mapped.priority = overrides.priority
            if overrides.labels:
                mapped.labels.extend(overrides.labels)
            if overrides.custom_fields:
                mapped.custom_fields.update(overrides.custom_fields)

        # Build issue payload
        issue_data = self._build_issue_payload(
            project_key=project_key,
            summary=mapped.summary,
            description=mapped.description,
            issue_type=mapped.issue_type,
            priority=mapped.priority,
            labels=mapped.labels,
            assignee_id=overrides.assignee_id if overrides else None,
            custom_fields=mapped.custom_fields,
        )

        # Create issue
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.API_BASE}/{tokens.cloud_id}/rest/api/3/issue",
                headers={"Authorization": f"Bearer {tokens.access_token}"},
                json=issue_data,
            )

            if not response.is_success:
                logger.error(
                    "Failed to create Jira issue",
                    status=response.status_code,
                    error=response.text,
                )
                raise ValueError(f"Failed to create issue: {response.text}")

            result = response.json()

        # Get full issue details
        issue = await self._get_issue(tokens, result["key"])

        # Store link
        await self._create_link(
            tenant_id=tenant_id,
            insight_id=insight["id"],
            jira_issue_id=result["id"],
            jira_issue_key=result["key"],
            project_key=project_key,
            issue_status=issue.get("fields", {}).get("status", {}).get("name"),
        )

        logger.info(
            "Jira issue created from insight",
            insight_id=insight["id"],
            issue_key=result["key"],
        )

        return JiraIssueResponse(
            id=result["id"],
            key=result["key"],
            self_url=result["self"],
            summary=issue["fields"]["summary"],
            status=issue["fields"]["status"]["name"],
            priority=issue["fields"].get("priority", {}).get("name"),
            assignee=issue["fields"].get("assignee", {}).get("displayName"),
            created=datetime.fromisoformat(issue["fields"]["created"].replace("Z", "+00:00")),
            updated=datetime.fromisoformat(issue["fields"]["updated"].replace("Z", "+00:00")),
            insight_id=insight["id"],
        )

    async def update_issue(
        self,
        tenant_id: str,
        issue_key: str,
        updates: dict[str, Any],
    ) -> JiraIssueResponse:
        """Update a Jira issue.

        Args:
            tenant_id: ASWA tenant identifier
            issue_key: Jira issue key
            updates: Fields to update

        Returns:
            Updated issue details
        """
        tokens = await self.oauth_handler.get_valid_tokens(tenant_id)
        if not tokens or not tokens.cloud_id:
            raise ValueError("Jira not connected")

        update_data = {"fields": {}}

        if "summary" in updates:
            update_data["fields"]["summary"] = updates["summary"]

        if "description" in updates:
            update_data["fields"]["description"] = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": updates["description"]}],
                    }
                ],
            }

        if "labels" in updates:
            update_data["fields"]["labels"] = updates["labels"]

        if "priority" in updates:
            update_data["fields"]["priority"] = {"name": updates["priority"]}

        if "assignee_id" in updates:
            update_data["fields"]["assignee"] = {"accountId": updates["assignee_id"]}

        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{self.API_BASE}/{tokens.cloud_id}/rest/api/3/issue/{issue_key}",
                headers={"Authorization": f"Bearer {tokens.access_token}"},
                json=update_data,
            )

            if not response.is_success:
                raise ValueError(f"Failed to update issue: {response.text}")

        # Get updated issue
        issue = await self._get_issue(tokens, issue_key)

        # Update link
        await self._update_link_status(tenant_id, issue_key, issue["fields"]["status"]["name"])

        logger.info("Jira issue updated", issue_key=issue_key)

        return JiraIssueResponse(
            id=issue["id"],
            key=issue["key"],
            self_url=issue["self"],
            summary=issue["fields"]["summary"],
            status=issue["fields"]["status"]["name"],
            priority=issue["fields"].get("priority", {}).get("name"),
            assignee=issue["fields"].get("assignee", {}).get("displayName"),
            created=datetime.fromisoformat(issue["fields"]["created"].replace("Z", "+00:00")),
            updated=datetime.fromisoformat(issue["fields"]["updated"].replace("Z", "+00:00")),
        )

    async def add_comment(
        self,
        tenant_id: str,
        issue_key: str,
        comment: str,
    ) -> dict[str, Any]:
        """Add a comment to an issue.

        Args:
            tenant_id: ASWA tenant identifier
            issue_key: Jira issue key
            comment: Comment text

        Returns:
            Comment data
        """
        tokens = await self.oauth_handler.get_valid_tokens(tenant_id)
        if not tokens or not tokens.cloud_id:
            raise ValueError("Jira not connected")

        comment_data = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": comment}],
                    }
                ],
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.API_BASE}/{tokens.cloud_id}/rest/api/3/issue/{issue_key}/comment",
                headers={"Authorization": f"Bearer {tokens.access_token}"},
                json=comment_data,
            )

            if not response.is_success:
                raise ValueError(f"Failed to add comment: {response.text}")

            result = response.json()

        logger.info("Comment added to Jira issue", issue_key=issue_key)

        return {
            "id": result["id"],
            "body": comment,
            "created": result["created"],
            "author": result.get("author", {}).get("displayName"),
        }

    async def transition_issue(
        self,
        tenant_id: str,
        issue_key: str,
        transition_name: str,
    ) -> JiraIssueResponse:
        """Transition an issue to a new status.

        Args:
            tenant_id: ASWA tenant identifier
            issue_key: Jira issue key
            transition_name: Target transition name

        Returns:
            Updated issue details
        """
        tokens = await self.oauth_handler.get_valid_tokens(tenant_id)
        if not tokens or not tokens.cloud_id:
            raise ValueError("Jira not connected")

        # Get available transitions
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.API_BASE}/{tokens.cloud_id}/rest/api/3/issue/{issue_key}/transitions",
                headers={"Authorization": f"Bearer {tokens.access_token}"},
            )

            if not response.is_success:
                raise ValueError("Failed to get transitions")

            transitions = response.json().get("transitions", [])

        # Find matching transition
        transition_id = None
        for t in transitions:
            if t["name"].lower() == transition_name.lower():
                transition_id = t["id"]
                break

        if not transition_id:
            available = [t["name"] for t in transitions]
            raise ValueError(f"Transition '{transition_name}' not found. Available: {available}")

        # Execute transition
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.API_BASE}/{tokens.cloud_id}/rest/api/3/issue/{issue_key}/transitions",
                headers={"Authorization": f"Bearer {tokens.access_token}"},
                json={"transition": {"id": transition_id}},
            )

            if not response.is_success:
                raise ValueError(f"Failed to transition: {response.text}")

        # Get updated issue
        issue = await self._get_issue(tokens, issue_key)

        # Update link status
        await self._update_link_status(tenant_id, issue_key, issue["fields"]["status"]["name"])

        logger.info(
            "Jira issue transitioned",
            issue_key=issue_key,
            new_status=issue["fields"]["status"]["name"],
        )

        return JiraIssueResponse(
            id=issue["id"],
            key=issue["key"],
            self_url=issue["self"],
            summary=issue["fields"]["summary"],
            status=issue["fields"]["status"]["name"],
            priority=issue["fields"].get("priority", {}).get("name"),
            assignee=issue["fields"].get("assignee", {}).get("displayName"),
            created=datetime.fromisoformat(issue["fields"]["created"].replace("Z", "+00:00")),
            updated=datetime.fromisoformat(issue["fields"]["updated"].replace("Z", "+00:00")),
        )

    async def get_issue(
        self,
        tenant_id: str,
        issue_key: str,
    ) -> JiraIssueResponse | None:
        """Get a Jira issue.

        Args:
            tenant_id: ASWA tenant identifier
            issue_key: Jira issue key

        Returns:
            Issue details or None
        """
        tokens = await self.oauth_handler.get_valid_tokens(tenant_id)
        if not tokens or not tokens.cloud_id:
            return None

        try:
            issue = await self._get_issue(tokens, issue_key)
        except Exception:
            return None

        # Get linked insight ID
        insight_id = await self._get_linked_insight(tenant_id, issue_key)

        return JiraIssueResponse(
            id=issue["id"],
            key=issue["key"],
            self_url=issue["self"],
            summary=issue["fields"]["summary"],
            status=issue["fields"]["status"]["name"],
            priority=issue["fields"].get("priority", {}).get("name"),
            assignee=issue["fields"].get("assignee", {}).get("displayName"),
            created=datetime.fromisoformat(issue["fields"]["created"].replace("Z", "+00:00")),
            updated=datetime.fromisoformat(issue["fields"]["updated"].replace("Z", "+00:00")),
            insight_id=insight_id,
        )

    async def get_issues_for_insight(
        self,
        tenant_id: str,
        insight_id: str,
    ) -> list[JiraIssueResponse]:
        """Get all Jira issues linked to an insight.

        Args:
            tenant_id: ASWA tenant identifier
            insight_id: ASWA insight ID

        Returns:
            List of linked issues
        """
        async with self.session_factory() as session:
            result = await session.execute(
                select(JiraIssueLinkDB).where(
                    JiraIssueLinkDB.tenant_id == tenant_id,
                    JiraIssueLinkDB.insight_id == insight_id,
                )
            )
            links = result.scalars().all()

        issues = []
        for link in links:
            issue = await self.get_issue(tenant_id, link.jira_issue_key)
            if issue:
                issues.append(issue)

        return issues

    async def search_issues(
        self,
        tenant_id: str,
        jql: str,
        max_results: int = 50,
    ) -> list[JiraIssueResponse]:
        """Search for issues using JQL.

        Args:
            tenant_id: ASWA tenant identifier
            jql: JQL query
            max_results: Maximum results

        Returns:
            List of matching issues
        """
        tokens = await self.oauth_handler.get_valid_tokens(tenant_id)
        if not tokens or not tokens.cloud_id:
            return []

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.API_BASE}/{tokens.cloud_id}/rest/api/3/search",
                headers={"Authorization": f"Bearer {tokens.access_token}"},
                params={"jql": jql, "maxResults": max_results},
            )

            if not response.is_success:
                logger.error("JQL search failed", error=response.text)
                return []

            data = response.json()

        issues = []
        for issue in data.get("issues", []):
            insight_id = await self._get_linked_insight(tenant_id, issue["key"])
            issues.append(JiraIssueResponse(
                id=issue["id"],
                key=issue["key"],
                self_url=issue["self"],
                summary=issue["fields"]["summary"],
                status=issue["fields"]["status"]["name"],
                priority=issue["fields"].get("priority", {}).get("name"),
                assignee=issue["fields"].get("assignee", {}).get("displayName"),
                created=datetime.fromisoformat(issue["fields"]["created"].replace("Z", "+00:00")),
                updated=datetime.fromisoformat(issue["fields"]["updated"].replace("Z", "+00:00")),
                insight_id=insight_id,
            ))

        return issues

    def _build_issue_payload(
        self,
        project_key: str,
        summary: str,
        description: str,
        issue_type: str,
        priority: str,
        labels: list[str],
        assignee_id: str | None = None,
        custom_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build Jira issue creation payload.

        Args:
            project_key: Project key
            summary: Issue summary
            description: Issue description
            issue_type: Issue type name
            priority: Priority name
            labels: Issue labels
            assignee_id: Optional assignee account ID
            custom_fields: Optional custom fields

        Returns:
            Issue creation payload
        """
        fields = {
            "project": {"key": project_key},
            "summary": summary,
            "description": {
                "type": "doc",
                "version": 1,
                "content": self._parse_description_to_adf(description),
            },
            "issuetype": {"name": issue_type},
            "priority": {"name": priority},
            "labels": labels,
        }

        if assignee_id:
            fields["assignee"] = {"accountId": assignee_id}

        if custom_fields:
            fields.update(custom_fields)

        return {"fields": fields}

    def _parse_description_to_adf(
        self,
        description: str,
    ) -> list[dict]:
        """Parse description text to Atlassian Document Format.

        Args:
            description: Plain text description

        Returns:
            ADF content blocks
        """
        content = []

        for paragraph in description.split("\n\n"):
            if paragraph.strip():
                # Handle special formatting
                if paragraph.startswith("h3. "):
                    content.append({
                        "type": "heading",
                        "attrs": {"level": 3},
                        "content": [{"type": "text", "text": paragraph[4:]}],
                    })
                elif paragraph.startswith("{quote}"):
                    quote_text = paragraph.replace("{quote}", "").strip()
                    content.append({
                        "type": "blockquote",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": quote_text}],
                            }
                        ],
                    })
                elif paragraph == "----":
                    content.append({"type": "rule"})
                else:
                    # Parse inline formatting
                    inline_content = self._parse_inline_formatting(paragraph)
                    content.append({
                        "type": "paragraph",
                        "content": inline_content,
                    })

        return content

    def _parse_inline_formatting(
        self,
        text: str,
    ) -> list[dict]:
        """Parse inline formatting to ADF.

        Args:
            text: Text with inline formatting

        Returns:
            ADF inline content
        """
        # Simple implementation - just return plain text
        # A full implementation would parse *bold*, _italic_, etc.
        return [{"type": "text", "text": text}]

    async def _get_issue(
        self,
        tokens,
        issue_key: str,
    ) -> dict[str, Any]:
        """Get issue details from Jira.

        Args:
            tokens: OAuth tokens
            issue_key: Issue key

        Returns:
            Issue data
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.API_BASE}/{tokens.cloud_id}/rest/api/3/issue/{issue_key}",
                headers={"Authorization": f"Bearer {tokens.access_token}"},
            )
            response.raise_for_status()
            return response.json()

    async def _create_link(
        self,
        tenant_id: str,
        insight_id: str,
        jira_issue_id: str,
        jira_issue_key: str,
        project_key: str,
        issue_status: str | None,
    ) -> None:
        """Create issue-insight link record.

        Args:
            tenant_id: Tenant ID
            insight_id: Insight ID
            jira_issue_id: Jira issue ID
            jira_issue_key: Jira issue key
            project_key: Project key
            issue_status: Current issue status
        """
        link = JiraIssueLinkDB(
            tenant_id=tenant_id,
            insight_id=insight_id,
            jira_issue_id=jira_issue_id,
            jira_issue_key=jira_issue_key,
            project_key=project_key,
            issue_status=issue_status,
            last_synced_at=datetime.utcnow(),
        )

        async with self.session_factory() as session:
            session.add(link)
            await session.commit()

    async def _update_link_status(
        self,
        tenant_id: str,
        issue_key: str,
        status: str,
    ) -> None:
        """Update link status.

        Args:
            tenant_id: Tenant ID
            issue_key: Jira issue key
            status: New status
        """
        from sqlalchemy import update

        async with self.session_factory() as session:
            await session.execute(
                update(JiraIssueLinkDB)
                .where(
                    JiraIssueLinkDB.tenant_id == tenant_id,
                    JiraIssueLinkDB.jira_issue_key == issue_key,
                )
                .values(
                    issue_status=status,
                    last_synced_at=datetime.utcnow(),
                )
            )
            await session.commit()

    async def _get_linked_insight(
        self,
        tenant_id: str,
        issue_key: str,
    ) -> str | None:
        """Get insight ID linked to an issue.

        Args:
            tenant_id: Tenant ID
            issue_key: Issue key

        Returns:
            Insight ID or None
        """
        async with self.session_factory() as session:
            result = await session.execute(
                select(JiraIssueLinkDB).where(
                    JiraIssueLinkDB.tenant_id == tenant_id,
                    JiraIssueLinkDB.jira_issue_key == issue_key,
                )
            )
            link = result.scalar_one_or_none()
            return link.insight_id if link else None
```

### 2. Create `/services/integration-service/src/aswa_integrations/api/jira_routes.py`
```python
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated, Any
import structlog

from aswa_integrations.jira.issue_manager import (
    JiraIssueManager,
    JiraIssueCreate,
    JiraIssueResponse,
)
from aswa_integrations.jira.connection import JiraConnectionStatus, JiraProject
from aswa_integrations.api.dependencies import get_tenant_id

logger = structlog.get_logger()
router = APIRouter(prefix="/jira", tags=["jira"])

_jira_manager: JiraIssueManager | None = None


def set_jira_manager(manager: JiraIssueManager) -> None:
    """Set the global Jira manager instance."""
    global _jira_manager
    _jira_manager = manager


def get_jira_manager() -> JiraIssueManager:
    """Get the Jira manager dependency."""
    if not _jira_manager:
        raise RuntimeError("Jira manager not initialized")
    return _jira_manager


@router.post("/issues", response_model=JiraIssueResponse, status_code=status.HTTP_201_CREATED)
async def create_issue(
    insight: dict[str, Any],
    project_key: str,
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    manager: Annotated[JiraIssueManager, Depends(get_jira_manager)],
    overrides: JiraIssueCreate | None = None,
) -> JiraIssueResponse:
    """Create a Jira issue from an insight."""
    try:
        return await manager.create_issue_from_insight(
            tenant_id, insight, project_key, overrides
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/issues/{issue_key}", response_model=JiraIssueResponse)
async def get_issue(
    issue_key: str,
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    manager: Annotated[JiraIssueManager, Depends(get_jira_manager)],
) -> JiraIssueResponse:
    """Get a Jira issue."""
    issue = await manager.get_issue(tenant_id, issue_key)
    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    return issue


@router.patch("/issues/{issue_key}", response_model=JiraIssueResponse)
async def update_issue(
    issue_key: str,
    updates: dict[str, Any],
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    manager: Annotated[JiraIssueManager, Depends(get_jira_manager)],
) -> JiraIssueResponse:
    """Update a Jira issue."""
    try:
        return await manager.update_issue(tenant_id, issue_key, updates)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/issues/{issue_key}/comments")
async def add_comment(
    issue_key: str,
    comment: str,
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    manager: Annotated[JiraIssueManager, Depends(get_jira_manager)],
) -> dict:
    """Add a comment to an issue."""
    try:
        return await manager.add_comment(tenant_id, issue_key, comment)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/issues/{issue_key}/transition", response_model=JiraIssueResponse)
async def transition_issue(
    issue_key: str,
    transition_name: str,
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    manager: Annotated[JiraIssueManager, Depends(get_jira_manager)],
) -> JiraIssueResponse:
    """Transition an issue to a new status."""
    try:
        return await manager.transition_issue(tenant_id, issue_key, transition_name)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/insights/{insight_id}/issues", response_model=list[JiraIssueResponse])
async def get_issues_for_insight(
    insight_id: str,
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    manager: Annotated[JiraIssueManager, Depends(get_jira_manager)],
) -> list[JiraIssueResponse]:
    """Get all Jira issues linked to an insight."""
    return await manager.get_issues_for_insight(tenant_id, insight_id)


@router.get("/search", response_model=list[JiraIssueResponse])
async def search_issues(
    jql: str,
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    manager: Annotated[JiraIssueManager, Depends(get_jira_manager)],
    max_results: int = 50,
) -> list[JiraIssueResponse]:
    """Search for issues using JQL."""
    return await manager.search_issues(tenant_id, jql, max_results)
```

## Test Requirements

### Create `/services/integration-service/tests/jira/test_issue_manager.py`
```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from aswa_integrations.jira.issue_manager import JiraIssueManager, JiraIssueCreate
from aswa_integrations.jira.oauth import JiraTokens


class TestJiraIssueManager:
    @pytest.fixture
    def mock_tokens(self):
        return JiraTokens(
            access_token="test-token",
            refresh_token="refresh-token",
            expires_at=datetime.utcnow(),
            scope="read:jira-work write:jira-work",
            cloud_id="cloud-123",
        )

    @pytest.fixture
    def sample_insight(self):
        return {
            "id": "insight-123",
            "type": "risk",
            "title": "Security Vulnerability",
            "description": "Critical security issue found",
            "severity": "critical",
            "confidence": 0.95,
            "document_name": "Security Report.pdf",
        }

    @pytest.mark.asyncio
    async def test_create_issue_from_insight(self, mock_tokens, sample_insight):
        """Test creating an issue from an insight."""
        oauth_handler = MagicMock()
        oauth_handler.get_valid_tokens = AsyncMock(return_value=mock_tokens)

        session_factory = MagicMock()

        manager = JiraIssueManager(oauth_handler, session_factory)

        # Mock project config
        with patch.object(manager.project_config, 'get_config', new_callable=AsyncMock) as mock_config:
            from aswa_integrations.jira.project_config import JiraProjectConfigResponse

            mock_config.return_value = JiraProjectConfigResponse(
                id="config-123",
                tenant_id="tenant-123",
                project_key="TEST",
                project_name="Test Project",
                risk_issue_type="Bug",
                opportunity_issue_type="Story",
                default_issue_type="Task",
                priority_mapping={"critical": "Highest"},
                auto_labels=["aswa"],
                include_severity_label=True,
                include_type_label=True,
                custom_field_mappings={},
                sync_enabled=True,
                sync_comments=True,
                sync_status=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )

            with patch('httpx.AsyncClient') as mock_client:
                mock_response = MagicMock()
                mock_response.is_success = True
                mock_response.json.return_value = {
                    "id": "10001",
                    "key": "TEST-123",
                    "self": "https://test.atlassian.net/rest/api/3/issue/10001",
                }

                mock_client_instance = AsyncMock()
                mock_client_instance.post = AsyncMock(return_value=mock_response)
                mock_client_instance.get = AsyncMock(return_value=MagicMock(
                    json=lambda: {
                        "id": "10001",
                        "key": "TEST-123",
                        "self": "https://test.atlassian.net/rest/api/3/issue/10001",
                        "fields": {
                            "summary": "[RISK] Security Vulnerability",
                            "status": {"name": "To Do"},
                            "priority": {"name": "Highest"},
                            "created": "2024-01-15T10:00:00Z",
                            "updated": "2024-01-15T10:00:00Z",
                        },
                    }
                ))
                mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                mock_client_instance.__aexit__ = AsyncMock()
                mock_client.return_value = mock_client_instance

                with patch.object(manager, '_create_link', new_callable=AsyncMock):
                    # This would require full setup, but we can verify the flow


class TestBuildIssuePayload:
    def test_build_payload_basic(self):
        """Test building basic issue payload."""
        manager = JiraIssueManager(MagicMock(), MagicMock())

        payload = manager._build_issue_payload(
            project_key="TEST",
            summary="Test Issue",
            description="Test description",
            issue_type="Bug",
            priority="High",
            labels=["aswa", "test"],
        )

        assert payload["fields"]["project"]["key"] == "TEST"
        assert payload["fields"]["summary"] == "Test Issue"
        assert payload["fields"]["issuetype"]["name"] == "Bug"
        assert payload["fields"]["priority"]["name"] == "High"
        assert "aswa" in payload["fields"]["labels"]

    def test_build_payload_with_assignee(self):
        """Test building payload with assignee."""
        manager = JiraIssueManager(MagicMock(), MagicMock())

        payload = manager._build_issue_payload(
            project_key="TEST",
            summary="Test Issue",
            description="Test description",
            issue_type="Task",
            priority="Medium",
            labels=[],
            assignee_id="user-123",
        )

        assert payload["fields"]["assignee"]["accountId"] == "user-123"
```

## Verification

1. Run tests: `pytest tests/jira/test_issue_manager.py -v`
2. Test issue creation with sample insight
3. Verify issue updates work correctly
4. Test comment addition
5. Verify transitions work
