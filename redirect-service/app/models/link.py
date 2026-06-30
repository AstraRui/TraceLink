"""ORM model for a shortened link."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Link(Base):
    __tablename__ = "links"

    id: Mapped[int] = mapped_column(primary_key=True)

    # The short code is the public identifier used in the redirect URL.
    short_code: Mapped[str] = mapped_column(String(8), unique=True, index=True)

    original_url: Mapped[str] = mapped_column(String(2048))

    # Owner = admin user id (set by the admin panel). NULL for anonymous links.
    owner_id: Mapped[int | None] = mapped_column(default=None, index=True)

    # Private links are hidden from public listings (the redirect still works,
    # since a short link is inherently shareable once handed out).
    is_private: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Optional time-to-live. NULL = never expires.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    def is_expired(self, now: datetime) -> bool:
        if self.expires_at is None:
            return False
        # We always store UTC. SQLite drops tzinfo on read, so re-attach it
        # before comparing to keep the check backend-agnostic.
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        return expires <= now
