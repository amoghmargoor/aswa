"""OAuth endpoints."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from aswa_common.logging import get_logger

from aswa_connector.dependencies import RedisClient, TenantCtx
from aswa_connector.framework.oauth import OAuthManager, OAuthProviderEnum

logger = get_logger(__name__)

router = APIRouter()


class AuthorizeRequest(BaseModel):
    """Request to start OAuth flow."""

    connector_type: str
    connection_id: UUID | None = None  # For re-auth


class AuthorizeResponse(BaseModel):
    """OAuth authorization response."""

    url: str
    state: str


@router.post("/{provider}/authorize", response_model=AuthorizeResponse)
async def authorize(
    provider: str,
    request: AuthorizeRequest,
    tenant: TenantCtx,
    redis: RedisClient,
) -> AuthorizeResponse:
    """Start OAuth authorization flow.

    Returns a URL to redirect the user to for authorization.
    """
    try:
        oauth_provider = OAuthProviderEnum(provider)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    oauth_manager = OAuthManager(redis)

    try:
        auth_url = await oauth_manager.get_authorization_url(
            provider=oauth_provider,
            tenant_id=tenant["tenant_id"],
            connector_type=request.connector_type,
            user_id=tenant.get("user_id"),
            connection_id=request.connection_id,
        )

        return AuthorizeResponse(
            url=auth_url.url,
            state=auth_url.state,
        )

    finally:
        await oauth_manager.close()


@router.get("/{provider}/callback")
async def callback(
    provider: str,
    code: str = Query(...),
    state: str = Query(...),
    error: str | None = Query(None),
    error_description: str | None = Query(None),
    redis: RedisClient = Depends(),
) -> dict[str, Any]:
    """OAuth callback endpoint.

    Handles the redirect from the OAuth provider after user authorization.
    """
    if error:
        logger.warning(f"OAuth error: {error} - {error_description}")
        raise HTTPException(
            status_code=400,
            detail={"error": error, "description": error_description},
        )

    try:
        oauth_provider = OAuthProviderEnum(provider)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    oauth_manager = OAuthManager(redis)

    try:
        result = await oauth_manager.exchange_code(
            provider=oauth_provider,
            code=code,
            state=state,
        )

        if not result.success:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": result.error,
                    "description": result.error_description,
                },
            )

        # Return tokens and context
        # In production, you might redirect to frontend with a code
        return {
            "success": True,
            "tenant_id": str(result.tenant_id) if result.tenant_id else None,
            "connection_id": str(result.connection_id) if result.connection_id else None,
            "connector_type": result.connector_type,
            "token_type": result.tokens.token_type if result.tokens else None,
            "expires_at": (
                result.tokens.expires_at.isoformat()
                if result.tokens and result.tokens.expires_at
                else None
            ),
        }

    finally:
        await oauth_manager.close()


@router.post("/{provider}/refresh")
async def refresh_token(
    provider: str,
    connection_id: UUID,
    tenant: TenantCtx,
    redis: RedisClient,
) -> dict[str, Any]:
    """Refresh OAuth tokens for a connection.

    This endpoint is typically called by the system when
    tokens are about to expire.
    """
    try:
        oauth_provider = OAuthProviderEnum(provider)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    # Get current tokens from database
    from aswa_connector.framework.oauth import TokenStore
    from aswa_connector.dependencies import get_db_session

    # Note: This is simplified - in production, use proper DI
    # token_store = TokenStore()
    # tokens = await token_store.get_tokens(db, connection_id, tenant["tenant_id"])

    # For now, return not implemented
    raise HTTPException(
        status_code=501,
        detail="Token refresh via API not yet implemented",
    )
