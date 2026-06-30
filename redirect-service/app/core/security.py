"""Internal service authentication.

Link management endpoints (create/list) are not public: only trusted internal
callers (the admin panel) may use them. They authenticate with a shared secret
passed in the ``X-Internal-Token`` header. The public redirect (`/{code}`) is
intentionally left open.
"""

import secrets

from fastapi import Header, HTTPException, status

from app.core.config import settings


async def require_internal_token(x_internal_token: str = Header(default="")) -> None:
    expected = settings.internal_api_token
    # Constant-time compare; also reject if the server token is unconfigured.
    if not expected or not secrets.compare_digest(x_internal_token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing internal token",
        )
