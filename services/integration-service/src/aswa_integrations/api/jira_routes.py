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
