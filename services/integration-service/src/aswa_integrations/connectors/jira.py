from typing import Any
import structlog

from aswa_integrations.connectors.base import BaseConnector

logger = structlog.get_logger()


class JiraConnector(BaseConnector):
    """Jira integration connector."""

    def __init__(
        self,
        config: dict[str, Any],
        credentials: dict[str, str] | None = None,
    ):
        super().__init__(config, credentials)
        self.base_url = config.get("base_url", "").rstrip("/")
        self.project_key = config.get("project_key")

    def _get_auth(self) -> tuple[str, str] | None:
        """Get authentication tuple."""
        email = self.credentials.get("email")
        api_token = self.credentials.get("api_token")
        if email and api_token:
            return (email, api_token)
        return None

    async def test_connection(self) -> bool:
        """Test connection to Jira.

        Returns:
            True if connection successful

        Raises:
            Exception if connection fails
        """
        url = f"{self.base_url}/rest/api/3/myself"
        auth = self._get_auth()

        response = await self._request("GET", url, auth=auth)
        data = response.json()

        logger.info(
            "Jira connection test successful",
            account_id=data.get("accountId"),
        )

        return True

    async def execute(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute a Jira action.

        Args:
            action: Action type (create_issue, update_issue, etc.)
            payload: Action payload

        Returns:
            Action result
        """
        actions = {
            "create_issue": self._create_issue,
            "update_issue": self._update_issue,
            "get_issue": self._get_issue,
            "add_comment": self._add_comment,
            "transition_issue": self._transition_issue,
            "search": self._search_issues,
        }

        handler = actions.get(action)
        if not handler:
            raise ValueError(f"Unknown action: {action}")

        return await handler(payload)

    async def _create_issue(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a Jira issue.

        Args:
            payload: Issue data

        Returns:
            Created issue data
        """
        url = f"{self.base_url}/rest/api/3/issue"
        auth = self._get_auth()

        issue_data = {
            "fields": {
                "project": {"key": payload.get("project_key", self.project_key)},
                "summary": payload["summary"],
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {"type": "text", "text": payload.get("description", "")}
                            ],
                        }
                    ],
                },
                "issuetype": {"name": payload.get("issue_type", "Task")},
            }
        }

        # Add optional fields
        if payload.get("priority"):
            issue_data["fields"]["priority"] = {"name": payload["priority"]}
        if payload.get("labels"):
            issue_data["fields"]["labels"] = payload["labels"]
        if payload.get("assignee"):
            issue_data["fields"]["assignee"] = {"accountId": payload["assignee"]}

        response = await self._request(
            "POST",
            url,
            auth=auth,
            json=issue_data,
        )

        result = response.json()
        logger.info("Jira issue created", issue_key=result.get("key"))

        return result

    async def _update_issue(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Update a Jira issue.

        Args:
            payload: Update data with issue_key

        Returns:
            Update result
        """
        issue_key = payload["issue_key"]
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}"
        auth = self._get_auth()

        update_data = {"fields": {}}

        if payload.get("summary"):
            update_data["fields"]["summary"] = payload["summary"]
        if payload.get("description"):
            update_data["fields"]["description"] = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": payload["description"]}],
                    }
                ],
            }
        if payload.get("labels"):
            update_data["fields"]["labels"] = payload["labels"]

        await self._request("PUT", url, auth=auth, json=update_data)

        logger.info("Jira issue updated", issue_key=issue_key)

        return {"key": issue_key, "updated": True}

    async def _get_issue(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Get a Jira issue.

        Args:
            payload: Contains issue_key

        Returns:
            Issue data
        """
        issue_key = payload["issue_key"]
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}"
        auth = self._get_auth()

        response = await self._request("GET", url, auth=auth)
        return response.json()

    async def _add_comment(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Add a comment to an issue.

        Args:
            payload: Contains issue_key and comment

        Returns:
            Comment data
        """
        issue_key = payload["issue_key"]
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}/comment"
        auth = self._get_auth()

        comment_data = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": payload["comment"]}],
                    }
                ],
            }
        }

        response = await self._request("POST", url, auth=auth, json=comment_data)

        logger.info("Jira comment added", issue_key=issue_key)

        return response.json()

    async def _transition_issue(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Transition an issue to a new status.

        Args:
            payload: Contains issue_key and transition_id

        Returns:
            Transition result
        """
        issue_key = payload["issue_key"]
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}/transitions"
        auth = self._get_auth()

        transition_data = {"transition": {"id": payload["transition_id"]}}

        await self._request("POST", url, auth=auth, json=transition_data)

        logger.info(
            "Jira issue transitioned",
            issue_key=issue_key,
            transition_id=payload["transition_id"],
        )

        return {"key": issue_key, "transitioned": True}

    async def _search_issues(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Search for issues using JQL.

        Args:
            payload: Contains jql query

        Returns:
            Search results
        """
        url = f"{self.base_url}/rest/api/3/search"
        auth = self._get_auth()

        params = {
            "jql": payload.get("jql", f"project = {self.project_key}"),
            "maxResults": payload.get("max_results", 50),
            "startAt": payload.get("start_at", 0),
        }

        response = await self._request("GET", url, auth=auth, params=params)
        return response.json()
