"""Tenant context model."""

from uuid import UUID

from pydantic import BaseModel, Field


class TenantContext(BaseModel):
    """Tenant context containing tenant and user information."""

    tenant_id: UUID
    user_id: UUID | None = None
    roles: set[str] = Field(default_factory=set)
    metadata: dict[str, str] = Field(default_factory=dict)

    def has_role(self, role: str) -> bool:
        """Check if user has a specific role.

        Args:
            role: The role to check

        Returns:
            True if user has the role
        """
        return role in self.roles or role.upper() in self.roles

    def is_admin(self) -> bool:
        """Check if user is an admin.

        Returns:
            True if user has admin role
        """
        return self.has_role("admin") or self.has_role("ADMIN")
