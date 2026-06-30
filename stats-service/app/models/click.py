"""ORM model for a recorded click event."""

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Click(Base):
    __tablename__ = "clicks"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Indexed: every aggregation filters/groups by short_code.
    short_code: Mapped[str] = mapped_column(String(8), index=True)

    # Raw request metadata.
    user_agent: Mapped[str | None] = mapped_column(String(512), default=None)
    referer: Mapped[str | None] = mapped_column(String(2048), default=None)
    ip_hash: Mapped[str | None] = mapped_column(String(64), default=None)

    # Parsed from the user-agent at ingest time, so aggregation is a plain
    # GROUP BY with no re-parsing.
    browser: Mapped[str | None] = mapped_column(String(64), default=None)
    os: Mapped[str | None] = mapped_column(String(64), default=None)
    device_type: Mapped[str | None] = mapped_column(String(16), default=None)

    # Indexed: clicks-by-day and time-range filters group/scan on this column.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, server_default=func.now()
    )
