"""Internal service authentication.

Destructive endpoints (deleting a link's clicks) require a shared secret in the
``X-Internal-Token`` header. Read-only stats and event ingestion stay open on
the internal network.
"""

import secrets

from fastapi import Header, HTTPException, status

from app.core.config import settings


async def require_internal_token(x_internal_token: str = Header(default="")) -> None:
    expected = settings.internal_api_token
    if not expected or not secrets.compare_digest(x_internal_token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing internal token",
        )
