"""Approval service for action approval workflows."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import structlog

from aswa_agents.core.models import Action, ActionContext
from aswa_agents.core.types import ActionStatus

logger = structlog.get_logger()


class ApprovalRequest:
    """Represents an approval request for an action."""

    def __init__(
        self,
        request_id: UUID,
        action_id: UUID,
        action_type: str,
        agent_name: str,
        tenant_id: str,
        confidence: float,
        parameters: dict[str, Any],
        created_at: datetime,
        expires_at: datetime | None = None,
    ):
        self.request_id = request_id
        self.action_id = action_id
        self.action_type = action_type
        self.agent_name = agent_name
        self.tenant_id = tenant_id
        self.confidence = confidence
        self.parameters = parameters
        self.created_at = created_at
        self.expires_at = expires_at
        self.status = "pending"
        self.decided_by: str | None = None
        self.decided_at: datetime | None = None
        self.decision_reason: str | None = None


class ApprovalService:
    """Service for managing action approval workflows.

    This service handles:
    1. Creating approval requests for actions requiring review
    2. Managing the approval queue
    3. Processing approval/rejection decisions
    4. Notifying relevant users about pending approvals
    """

    def __init__(self, notification_client: Any = None):
        self._pending_approvals: dict[UUID, ApprovalRequest] = {}
        self.notification_client = notification_client
        self._logger = logger.bind(component="approval_service")

    async def request_approval(
        self,
        action: Action,
        context: ActionContext,
        agent_name: str,
    ) -> UUID:
        """
        Create an approval request for an action.

        Args:
            action: The action requiring approval
            context: Execution context
            agent_name: Name of the agent requesting approval

        Returns:
            Approval request ID
        """
        request_id = uuid4()

        approval_request = ApprovalRequest(
            request_id=request_id,
            action_id=action.id,
            action_type=action.type.value,
            agent_name=agent_name,
            tenant_id=context.tenant_id,
            confidence=action.confidence,
            parameters=action.parameters,
            created_at=datetime.now(timezone.utc),
        )

        self._pending_approvals[request_id] = approval_request

        self._logger.info(
            "Approval request created",
            request_id=str(request_id),
            action_id=str(action.id),
            action_type=action.type.value,
            agent_name=agent_name,
            confidence=action.confidence,
        )

        # Send notification if client is available
        if self.notification_client:
            await self._send_approval_notification(approval_request)

        return request_id

    async def approve(
        self,
        request_id: UUID,
        approved_by: str,
        reason: str | None = None,
    ) -> bool:
        """
        Approve a pending approval request.

        Args:
            request_id: The approval request ID
            approved_by: User ID who approved
            reason: Optional reason for approval

        Returns:
            True if approved successfully
        """
        request = self._pending_approvals.get(request_id)
        if not request:
            self._logger.warning("Approval request not found", request_id=str(request_id))
            return False

        if request.status != "pending":
            self._logger.warning(
                "Approval request already processed",
                request_id=str(request_id),
                status=request.status,
            )
            return False

        request.status = "approved"
        request.decided_by = approved_by
        request.decided_at = datetime.now(timezone.utc)
        request.decision_reason = reason

        self._logger.info(
            "Approval request approved",
            request_id=str(request_id),
            approved_by=approved_by,
        )

        return True

    async def reject(
        self,
        request_id: UUID,
        rejected_by: str,
        reason: str | None = None,
    ) -> bool:
        """
        Reject a pending approval request.

        Args:
            request_id: The approval request ID
            rejected_by: User ID who rejected
            reason: Optional reason for rejection

        Returns:
            True if rejected successfully
        """
        request = self._pending_approvals.get(request_id)
        if not request:
            self._logger.warning("Approval request not found", request_id=str(request_id))
            return False

        if request.status != "pending":
            self._logger.warning(
                "Approval request already processed",
                request_id=str(request_id),
                status=request.status,
            )
            return False

        request.status = "rejected"
        request.decided_by = rejected_by
        request.decided_at = datetime.now(timezone.utc)
        request.decision_reason = reason

        self._logger.info(
            "Approval request rejected",
            request_id=str(request_id),
            rejected_by=rejected_by,
            reason=reason,
        )

        return True

    async def get_pending_approvals(
        self,
        tenant_id: str,
        agent_name: str | None = None,
    ) -> list[ApprovalRequest]:
        """
        Get pending approval requests for a tenant.

        Args:
            tenant_id: The tenant ID
            agent_name: Optional filter by agent name

        Returns:
            List of pending approval requests
        """
        return [
            request
            for request in self._pending_approvals.values()
            if request.tenant_id == tenant_id
            and request.status == "pending"
            and (agent_name is None or request.agent_name == agent_name)
        ]

    async def get_request(self, request_id: UUID) -> ApprovalRequest | None:
        """Get an approval request by ID."""
        return self._pending_approvals.get(request_id)

    async def get_request_by_action(self, action_id: UUID) -> ApprovalRequest | None:
        """Get an approval request by action ID."""
        for request in self._pending_approvals.values():
            if request.action_id == action_id:
                return request
        return None

    async def _send_approval_notification(self, request: ApprovalRequest) -> None:
        """Send notification about a new approval request."""
        if not self.notification_client:
            return

        try:
            await self.notification_client.send(
                tenant_id=request.tenant_id,
                channel="slack",
                message={
                    "type": "approval_required",
                    "request_id": str(request.request_id),
                    "action_type": request.action_type,
                    "agent_name": request.agent_name,
                    "confidence": request.confidence,
                },
            )
        except Exception as e:
            self._logger.warning(
                "Failed to send approval notification",
                error=str(e),
            )

    def count_pending(self, tenant_id: str | None = None) -> int:
        """Count pending approvals."""
        if tenant_id:
            return sum(
                1
                for r in self._pending_approvals.values()
                if r.status == "pending" and r.tenant_id == tenant_id
            )
        return sum(1 for r in self._pending_approvals.values() if r.status == "pending")

    def clear(self) -> None:
        """Clear all approval requests. Useful for testing."""
        self._pending_approvals.clear()
