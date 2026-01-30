"""Agent versioning and audit logging."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
import structlog

logger = structlog.get_logger()


class VersionStatus(str, Enum):
    """Status of an agent version."""

    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class AuditAction(str, Enum):
    """Actions that can be audited."""

    AGENT_CREATED = "agent.created"
    AGENT_UPDATED = "agent.updated"
    AGENT_DELETED = "agent.deleted"
    AGENT_ACTIVATED = "agent.activated"
    AGENT_DEACTIVATED = "agent.deactivated"
    AGENT_EXECUTED = "agent.executed"
    AGENT_EXECUTION_FAILED = "agent.execution_failed"
    VERSION_CREATED = "version.created"
    VERSION_PUBLISHED = "version.published"
    VERSION_ROLLBACK = "version.rollback"
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_APPROVED = "approval.approved"
    APPROVAL_REJECTED = "approval.rejected"
    ACCESS_GRANTED = "access.granted"
    ACCESS_REVOKED = "access.revoked"


class AgentVersion(BaseModel):
    """A version of an agent definition."""

    id: UUID = Field(default_factory=uuid4)
    agent_id: UUID
    version_number: int
    status: VersionStatus = VersionStatus.DRAFT
    definition: dict[str, Any] = Field(default_factory=dict)
    changelog: str = ""
    created_by: UUID
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    published_at: datetime | None = None
    published_by: UUID | None = None


class VersionDiff(BaseModel):
    """Difference between two versions."""

    from_version: int
    to_version: int
    changes: list[dict[str, Any]] = Field(default_factory=list)
    summary: str = ""


class AuditEntry(BaseModel):
    """An audit log entry."""

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    action: AuditAction
    actor_id: UUID
    actor_type: str = "user"  # user, system, agent
    resource_type: str = "agent"
    resource_id: UUID | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    ip_address: str | None = None
    user_agent: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class VersionManager:
    """Manages agent versions."""

    def __init__(self, tenant_id: UUID):
        self.tenant_id = tenant_id
        self._versions: dict[UUID, list[AgentVersion]] = {}  # agent_id -> versions
        self._logger = logger.bind(
            component="VersionManager",
            tenant_id=str(tenant_id),
        )

    async def create_version(
        self,
        agent_id: UUID,
        definition: dict[str, Any],
        created_by: UUID,
        changelog: str = "",
    ) -> AgentVersion:
        """Create a new version of an agent."""
        versions = self._versions.setdefault(agent_id, [])

        # Determine version number
        version_number = 1
        if versions:
            version_number = max(v.version_number for v in versions) + 1

        version = AgentVersion(
            agent_id=agent_id,
            version_number=version_number,
            definition=definition,
            changelog=changelog,
            created_by=created_by,
        )

        versions.append(version)

        self._logger.info(
            "Version created",
            agent_id=str(agent_id),
            version=version_number,
        )

        return version

    async def publish_version(
        self,
        agent_id: UUID,
        version_id: UUID,
        published_by: UUID,
    ) -> AgentVersion:
        """Publish a version, making it the active version."""
        versions = self._versions.get(agent_id, [])

        # Find the version
        version = next((v for v in versions if v.id == version_id), None)
        if not version:
            raise ValueError(f"Version {version_id} not found")

        # Deprecate current published version
        for v in versions:
            if v.status == VersionStatus.PUBLISHED:
                v.status = VersionStatus.DEPRECATED

        # Publish new version
        version.status = VersionStatus.PUBLISHED
        version.published_at = datetime.now(timezone.utc)
        version.published_by = published_by

        self._logger.info(
            "Version published",
            agent_id=str(agent_id),
            version=version.version_number,
        )

        return version

    async def get_versions(
        self,
        agent_id: UUID,
        status: VersionStatus | None = None,
    ) -> list[AgentVersion]:
        """Get all versions of an agent."""
        versions = self._versions.get(agent_id, [])
        if status:
            versions = [v for v in versions if v.status == status]
        return sorted(versions, key=lambda v: v.version_number, reverse=True)

    async def get_version(
        self,
        agent_id: UUID,
        version_number: int | None = None,
    ) -> AgentVersion | None:
        """Get a specific version or the current published version."""
        versions = self._versions.get(agent_id, [])

        if version_number is not None:
            return next(
                (v for v in versions if v.version_number == version_number),
                None,
            )

        # Return current published version
        return next(
            (v for v in versions if v.status == VersionStatus.PUBLISHED),
            None,
        )

    async def rollback(
        self,
        agent_id: UUID,
        target_version: int,
        rolled_back_by: UUID,
    ) -> AgentVersion:
        """Rollback to a previous version."""
        versions = self._versions.get(agent_id, [])

        # Find target version
        target = next(
            (v for v in versions if v.version_number == target_version),
            None,
        )
        if not target:
            raise ValueError(f"Version {target_version} not found")

        # Create new version from target
        new_version = await self.create_version(
            agent_id=agent_id,
            definition=target.definition.copy(),
            created_by=rolled_back_by,
            changelog=f"Rollback to version {target_version}",
        )

        # Publish new version
        await self.publish_version(agent_id, new_version.id, rolled_back_by)

        self._logger.info(
            "Version rolled back",
            agent_id=str(agent_id),
            from_version=target_version,
            to_version=new_version.version_number,
        )

        return new_version

    async def diff_versions(
        self,
        agent_id: UUID,
        from_version: int,
        to_version: int,
    ) -> VersionDiff:
        """Get differences between two versions."""
        versions = self._versions.get(agent_id, [])

        from_v = next((v for v in versions if v.version_number == from_version), None)
        to_v = next((v for v in versions if v.version_number == to_version), None)

        if not from_v or not to_v:
            raise ValueError("Version not found")

        changes = self._calculate_diff(from_v.definition, to_v.definition)

        return VersionDiff(
            from_version=from_version,
            to_version=to_version,
            changes=changes,
            summary=f"{len(changes)} changes between v{from_version} and v{to_version}",
        )

    def _calculate_diff(
        self,
        old: dict[str, Any],
        new: dict[str, Any],
        path: str = "",
    ) -> list[dict[str, Any]]:
        """Calculate differences between two definitions."""
        changes = []

        all_keys = set(old.keys()) | set(new.keys())

        for key in all_keys:
            current_path = f"{path}.{key}" if path else key
            old_value = old.get(key)
            new_value = new.get(key)

            if key not in old:
                changes.append({
                    "type": "added",
                    "path": current_path,
                    "value": new_value,
                })
            elif key not in new:
                changes.append({
                    "type": "removed",
                    "path": current_path,
                    "value": old_value,
                })
            elif old_value != new_value:
                if isinstance(old_value, dict) and isinstance(new_value, dict):
                    changes.extend(self._calculate_diff(old_value, new_value, current_path))
                else:
                    changes.append({
                        "type": "modified",
                        "path": current_path,
                        "old_value": old_value,
                        "new_value": new_value,
                    })

        return changes


class AuditLogger:
    """Logs audit events."""

    def __init__(self, tenant_id: UUID):
        self.tenant_id = tenant_id
        self._entries: list[AuditEntry] = []
        self._logger = logger.bind(
            component="AuditLogger",
            tenant_id=str(tenant_id),
        )

    async def log(
        self,
        action: AuditAction,
        actor_id: UUID,
        resource_id: UUID | None = None,
        resource_type: str = "agent",
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditEntry:
        """Log an audit event."""
        entry = AuditEntry(
            tenant_id=self.tenant_id,
            action=action,
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )

        self._entries.append(entry)

        self._logger.info(
            "Audit event logged",
            action=action,
            actor_id=str(actor_id),
            resource_id=str(resource_id) if resource_id else None,
        )

        return entry

    async def query(
        self,
        action: AuditAction | None = None,
        actor_id: UUID | None = None,
        resource_id: UUID | None = None,
        resource_type: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEntry]:
        """Query audit entries."""
        results = self._entries

        if action:
            results = [e for e in results if e.action == action]
        if actor_id:
            results = [e for e in results if e.actor_id == actor_id]
        if resource_id:
            results = [e for e in results if e.resource_id == resource_id]
        if resource_type:
            results = [e for e in results if e.resource_type == resource_type]
        if from_date:
            results = [e for e in results if e.timestamp >= from_date]
        if to_date:
            results = [e for e in results if e.timestamp <= to_date]

        # Sort by timestamp descending
        results = sorted(results, key=lambda e: e.timestamp, reverse=True)

        return results[offset:offset + limit]

    async def get_activity_summary(
        self,
        resource_id: UUID,
        days: int = 7,
    ) -> dict[str, Any]:
        """Get activity summary for a resource."""
        from datetime import timedelta

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        entries = [
            e for e in self._entries
            if e.resource_id == resource_id and e.timestamp >= cutoff
        ]

        action_counts: dict[str, int] = {}
        for entry in entries:
            action_counts[entry.action.value] = action_counts.get(entry.action.value, 0) + 1

        unique_actors = len(set(e.actor_id for e in entries))

        return {
            "resource_id": str(resource_id),
            "period_days": days,
            "total_events": len(entries),
            "unique_actors": unique_actors,
            "action_counts": action_counts,
            "recent_events": [e.model_dump() for e in entries[:10]],
        }
