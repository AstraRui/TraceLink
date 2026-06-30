"""Create the first admin user from env settings, if it does not exist yet."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.models.user import User


async def ensure_admin_user(session: AsyncSession) -> None:
    existing = await session.scalar(select(User).where(User.username == settings.admin_username))
    if existing is not None:
        return
    session.add(
        User(
            username=settings.admin_username,
            hashed_password=hash_password(settings.admin_password),
        )
    )
    await session.commit()
