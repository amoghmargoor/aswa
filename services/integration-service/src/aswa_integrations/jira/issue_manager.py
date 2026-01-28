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
    summary: str | None = None
    description: str | None = None
    issue_type: str | None = None
    priority: str | None = None
    labels: list[str] | None = None
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
        """Initialize issue manager."""
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
        """Create a Jira issue from an ASWA insight."""
        tokens = await self.oauth_handler.get_valid_tokens(tenant_id)
        if not tokens or not tokens.cloud_id:
            raise ValueError("Jira not connected")

        config = await self.project_config.get_config(tenant_id, project_key)
        if not config:
            raise ValueError(f"Project {project_key} not configured")

        mapper = JiraFieldMapper(config)
        mapped = mapper.map_insight_to_issue(insight)

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

        issue = await self._get_issue(tokens, result["key"])

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
        """Update a Jira issue."""
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

        issue = await self._get_issue(tokens, issue_key)
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
        """Add a comment to an issue."""
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
        """Transition an issue to a new status."""
        tokens = await self.oauth_handler.get_valid_tokens(tenant_id)
        if not tokens or not tokens.cloud_id:
            raise ValueError("Jira not connected")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.API_BASE}/{tokens.cloud_id}/rest/api/3/issue/{issue_key}/transitions",
                headers={"Authorization": f"Bearer {tokens.access_token}"},
            )

            if not response.is_success:
                raise ValueError("Failed to get transitions")

            transitions = response.json().get("transitions", [])

        transition_id = None
        for t in transitions:
            if t["name"].lower() == transition_name.lower():
                transition_id = t["id"]
                break

        if not transition_id:
            available = [t["name"] for t in transitions]
            raise ValueError(f"Transition '{transition_name}' not found. Available: {available}")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.API_BASE}/{tokens.cloud_id}/rest/api/3/issue/{issue_key}/transitions",
                headers={"Authorization": f"Bearer {tokens.access_token}"},
                json={"transition": {"id": transition_id}},
            )

            if not response.is_success:
                raise ValueError(f"Failed to transition: {response.text}")

        issue = await self._get_issue(tokens, issue_key)
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
        """Get a Jira issue."""
        tokens = await self.oauth_handler.get_valid_tokens(tenant_id)
        if not tokens or not tokens.cloud_id:
            return None

        try:
            issue = await self._get_issue(tokens, issue_key)
        except Exception:
            return None

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
        """Get all Jira issues linked to an insight."""
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
        """Search for issues using JQL."""
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
        """Build Jira issue creation payload."""
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

    def _parse_description_to_adf(self, description: str) -> list[dict]:
        """Parse description text to Atlassian Document Format."""
        content = []

        for paragraph in description.split("\n\n"):
            if paragraph.strip():
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
                    inline_content = self._parse_inline_formatting(paragraph)
                    content.append({
                        "type": "paragraph",
                        "content": inline_content,
                    })

        return content

    def _parse_inline_formatting(self, text: str) -> list[dict]:
        """Parse inline formatting to ADF."""
        return [{"type": "text", "text": text}]

    async def _get_issue(self, tokens, issue_key: str) -> dict[str, Any]:
        """Get issue details from Jira."""
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
        """Create issue-insight link record."""
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
        """Update link status."""
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
        """Get insight ID linked to an issue."""
        async with self.session_factory() as session:
            result = await session.execute(
                select(JiraIssueLinkDB).where(
                    JiraIssueLinkDB.tenant_id == tenant_id,
                    JiraIssueLinkDB.jira_issue_key == issue_key,
                )
            )
            link = result.scalar_one_or_none()
            return link.insight_id if link else None
