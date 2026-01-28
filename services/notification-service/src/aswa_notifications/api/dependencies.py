from fastapi import Header, HTTPException, status


async def get_tenant_id(
    x_tenant_id: str = Header(alias="X-Tenant-ID"),
) -> str:
    """Get tenant ID from header."""
    if not x_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Tenant-ID header required",
        )
    return x_tenant_id


async def get_user_id(
    x_user_id: str = Header(alias="X-User-ID"),
) -> str:
    """Get user ID from header."""
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-User-ID header required",
        )
    return x_user_id
