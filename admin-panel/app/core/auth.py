"""JWT cookie authentication: the dependency that guards protected routes.

`get_current_user` reads the HttpOnly cookie, verifies the JWT and loads the
user. On any failure it raises `NotAuthenticatedError`, which an exception
handler (registered in main.py) turns into a redirect to the login page — so
protecting a page route is just ``Depends(get_current_user)``.
"""

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decode_token
from app.db.session import get_session
from app.models.user import User


class NotAuthenticatedError(Exception):
    """Raised when a protected route is accessed without a valid session."""


async def get_current_user(request: Request, session: AsyncSession = Depends(get_session)) -> User:
    token = request.cookies.get(settings.cookie_name)
    if not token:
        raise NotAuthenticatedError
    username = decode_token(token)
    if username is None:
        raise NotAuthenticatedError
    user = await session.scalar(select(User).where(User.username == username))
    if user is None:
        raise NotAuthenticatedError
    return user
