"""Tests for first-admin bootstrapping."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import verify_password
from app.models.user import User
from app.services.bootstrap import ensure_admin_user


async def test_bootstrap_creates_admin(session: AsyncSession) -> None:
    await ensure_admin_user(session)
    admin = await session.scalar(select(User).where(User.username == settings.admin_username))
    assert admin is not None
    assert verify_password(settings.admin_password, admin.hashed_password)


async def test_bootstrap_is_idempotent(session: AsyncSession) -> None:
    await ensure_admin_user(session)
    await ensure_admin_user(session)
    count = await session.scalar(select(func.count()).select_from(User))
    assert count == 1
