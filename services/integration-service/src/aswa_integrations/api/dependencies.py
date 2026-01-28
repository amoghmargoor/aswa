from fastapi import Request, HTTPException, status
from aswa_integrations.services.integration_manager import IntegrationManager

_integration_manager: IntegrationManager | None = None


def set_integration_manager(manager: IntegrationManager) -> None:
    """Set the global integration manager instance."""
    global _integration_manager
    _integration_manager = manager


def get_integration_manager() -> IntegrationManager:
    """Get the integration manager dependency."""
    if not _integration_manager:
        raise RuntimeError("Integration manager not initialized")
    return _integration_manager


def get_tenant_id(request: Request) -> str:
    """Extract tenant ID from request headers."""
    tenant_id = request.headers.get("X-Tenant-ID")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Tenant-ID header is required",
        )
    return tenant_id
