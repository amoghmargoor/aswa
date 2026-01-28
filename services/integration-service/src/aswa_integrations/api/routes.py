from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated
import structlog

from aswa_integrations.models.integration import (
    IntegrationCreate,
    IntegrationUpdate,
    IntegrationResponse,
    IntegrationType,
    IntegrationStatus,
)
from aswa_integrations.services.integration_manager import IntegrationManager
from aswa_integrations.api.dependencies import get_integration_manager, get_tenant_id

logger = structlog.get_logger()
router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.post("", response_model=IntegrationResponse, status_code=status.HTTP_201_CREATED)
async def create_integration(
    data: IntegrationCreate,
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    manager: Annotated[IntegrationManager, Depends(get_integration_manager)],
) -> IntegrationResponse:
    """Create a new integration."""
    return await manager.create_integration(tenant_id, data)


@router.get("", response_model=list[IntegrationResponse])
async def list_integrations(
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    manager: Annotated[IntegrationManager, Depends(get_integration_manager)],
    type: IntegrationType | None = None,
    status: IntegrationStatus | None = None,
) -> list[IntegrationResponse]:
    """List all integrations for a tenant."""
    return await manager.list_integrations(tenant_id, type, status)


@router.get("/{integration_id}", response_model=IntegrationResponse)
async def get_integration(
    integration_id: str,
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    manager: Annotated[IntegrationManager, Depends(get_integration_manager)],
) -> IntegrationResponse:
    """Get an integration by ID."""
    integration = await manager.get_integration(tenant_id, integration_id)
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found",
        )
    return integration


@router.patch("/{integration_id}", response_model=IntegrationResponse)
async def update_integration(
    integration_id: str,
    data: IntegrationUpdate,
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    manager: Annotated[IntegrationManager, Depends(get_integration_manager)],
) -> IntegrationResponse:
    """Update an integration."""
    integration = await manager.update_integration(tenant_id, integration_id, data)
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found",
        )
    return integration


@router.delete("/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_integration(
    integration_id: str,
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    manager: Annotated[IntegrationManager, Depends(get_integration_manager)],
) -> None:
    """Delete an integration."""
    deleted = await manager.delete_integration(tenant_id, integration_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found",
        )


@router.post("/{integration_id}/test")
async def test_integration(
    integration_id: str,
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    manager: Annotated[IntegrationManager, Depends(get_integration_manager)],
) -> dict:
    """Test an integration connection."""
    connector = await manager.get_connector(tenant_id, integration_id)
    if not connector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found or disabled",
        )

    try:
        async with connector:
            await connector.test_connection()
        return {"status": "success", "message": "Connection test passed"}
    except Exception as e:
        logger.error("Integration test failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Connection test failed: {str(e)}",
        )


@router.post("/{integration_id}/execute")
async def execute_integration_action(
    integration_id: str,
    action: str,
    payload: dict,
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    manager: Annotated[IntegrationManager, Depends(get_integration_manager)],
) -> dict:
    """Execute an action on an integration."""
    connector = await manager.get_connector(tenant_id, integration_id)
    if not connector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found or disabled",
        )

    try:
        async with connector:
            result = await connector.execute(action, payload)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error("Integration action failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Action failed: {str(e)}",
        )
