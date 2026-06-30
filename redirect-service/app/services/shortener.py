"""Short-code generation and link create/resolve logic.

The pieces are deliberately split so each is unit-testable in isolation:

* ``generate_code``       — pure function, ``choice`` is injectable for
                            deterministic tests; defaults to ``secrets.choice``
                            so production codes are unguessable.
* ``find_unique_code``    — collision-retry loop with an injectable async
                            ``exists`` predicate, so the retry behaviour can be
                            tested without a database.
* ``LinkService``         — wires the above to the real DB session.
"""

import secrets
import string
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, settings
from app.models.link import Link
from app.schemas.link import LinkCreate

# base62: digits + upper + lower. URL-safe, no ambiguous separators.
ALPHABET = string.ascii_letters + string.digits

MIN_LENGTH = 6
MAX_LENGTH = 8
DEFAULT_MAX_ATTEMPTS = 10


class ShortCodeCollisionError(RuntimeError):
    """Raised when a unique code could not be found within the retry budget."""


def generate_code(
    length: int = 7,
    *,
    alphabet: str = ALPHABET,
    choice: Callable[[str], str] = secrets.choice,
) -> str:
    """Return one random short code of ``length`` chars from ``alphabet``.

    ``choice`` is injectable: tests pass a deterministic picker, production uses
    ``secrets.choice`` (cryptographically strong, so codes can't be enumerated).
    """
    if not MIN_LENGTH <= length <= MAX_LENGTH:
        raise ValueError(f"short code length must be between {MIN_LENGTH} and {MAX_LENGTH}")
    return "".join(choice(alphabet) for _ in range(length))


async def find_unique_code(
    exists: Callable[[str], Awaitable[bool]],
    *,
    length: int = 7,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    make_code: Callable[[int], str] = generate_code,
) -> str:
    """Generate codes until one is not already taken.

    ``exists`` is an async predicate (DB lookup in production, a set in tests).
    Raises :class:`ShortCodeCollisionError` if every attempt collides.
    """
    for _ in range(max_attempts):
        code = make_code(length)
        if not await exists(code):
            return code
    raise ShortCodeCollisionError(f"no unique short code after {max_attempts} attempts")


class LinkService:
    """Persistence-facing operations for links."""

    def __init__(self, session: AsyncSession, config: Settings = settings) -> None:
        self.session = session
        self.config = config

    async def _code_exists(self, code: str) -> bool:
        found = await self.session.scalar(select(Link.id).where(Link.short_code == code))
        return found is not None

    def _resolve_expiry(self, ttl_days: int | None) -> datetime | None:
        days = ttl_days if ttl_days is not None else self.config.default_link_ttl_days
        if not days:
            return None
        return datetime.now(UTC) + timedelta(days=days)

    async def create(self, payload: LinkCreate) -> Link:
        code = await find_unique_code(self._code_exists, length=self.config.short_code_length)
        link = Link(
            short_code=code,
            original_url=str(payload.original_url),
            owner_id=payload.owner_id,
            is_private=payload.is_private,
            expires_at=self._resolve_expiry(payload.ttl_days),
        )
        self.session.add(link)
        await self.session.commit()
        await self.session.refresh(link)
        return link

    async def resolve(self, code: str) -> Link | None:
        """Return the live link for ``code``, or None if missing/expired."""
        link = await self.session.scalar(select(Link).where(Link.short_code == code))
        if link is None or link.is_expired(datetime.now(UTC)):
            return None
        return link

    async def delete(self, code: str) -> bool:
        """Delete a link by code. Returns True if a row was removed."""
        link = await self.session.scalar(select(Link).where(Link.short_code == code))
        if link is None:
            return False
        await self.session.delete(link)
        await self.session.commit()
        return True
