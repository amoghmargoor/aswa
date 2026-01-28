from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated
from pydantic import BaseModel
import structlog

from aswa_notifications.channels.push import DeviceTokenManager
from aswa_notifications.api.dependencies import get_tenant_id, get_user_id

logger = structlog.get_logger()
router = APIRouter(prefix="/push", tags=["push"])

_token_manager: DeviceTokenManager | None = None


def set_token_manager(manager: DeviceTokenManager) -> None:
    """Set the global token manager instance."""
    global _token_manager
    _token_manager = manager


def get_token_manager() -> DeviceTokenManager:
    """Get the token manager dependency."""
    if not _token_manager:
        raise RuntimeError("Token manager not initialized")
    return _token_manager


class RegisterTokenRequest(BaseModel):
    """Request to register a push token."""
    token: str
    platform: str  # fcm, apns
    device_name: str | None = None
    device_model: str | None = None
    os_version: str | None = None
    app_version: str | None = None


class UnregisterTokenRequest(BaseModel):
    """Request to unregister a push token."""
    token: str


@router.post("/tokens")
async def register_push_token(
    request: RegisterTokenRequest,
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    user_id: Annotated[str, Depends(get_user_id)],
    manager: Annotated[DeviceTokenManager, Depends(get_token_manager)],
) -> dict:
    """Register a device push token."""
    device_info = {
        "device_name": request.device_name,
        "device_model": request.device_model,
        "os_version": request.os_version,
        "app_version": request.app_version,
    }

    await manager.register_token(
        tenant_id=tenant_id,
        user_id=user_id,
        token=request.token,
        platform=request.platform,
        device_info=device_info,
    )

    return {"status": "registered"}


@router.delete("/tokens")
async def unregister_push_token(
    request: UnregisterTokenRequest,
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    user_id: Annotated[str, Depends(get_user_id)],
    manager: Annotated[DeviceTokenManager, Depends(get_token_manager)],
) -> dict:
    """Unregister a device push token."""
    await manager.unregister_token(
        tenant_id=tenant_id,
        user_id=user_id,
        token=request.token,
    )

    return {"status": "unregistered"}


@router.get("/tokens")
async def list_push_tokens(
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    user_id: Annotated[str, Depends(get_user_id)],
    manager: Annotated[DeviceTokenManager, Depends(get_token_manager)],
) -> list[dict]:
    """List all registered push tokens for the user."""
    tokens = await manager.get_user_tokens(tenant_id, user_id)

    # Don't expose full tokens
    return [
        {
            "platform": t.get("platform"),
            "device_info": t.get("device_info", {}),
            "registered_at": t.get("registered_at"),
            "token_preview": t.get("token", "")[:20] + "...",
        }
        for t in tokens
    ]
