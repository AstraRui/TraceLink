"""HTTP routes: link-management API + the public short-link redirect."""

import hashlib
from datetime import UTC, datetime

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import trace_id_var
from app.core.security import require_internal_token
from app.db.session import get_session
from app.models.link import Link
from app.schemas.event import ClickEvent
from app.schemas.link import LinkCreate, LinkRead
from app.services.cache import LinkCache, get_cache
from app.services.events import ClickEmitter, get_click_emitter
from app.services.shortener import LinkService

# 302 (not 301): a temporary redirect is not cached by the browser, so every
# click reaches the service and is counted in the stats.
REDIRECT_STATUS = status.HTTP_302_FOUND

api_router = APIRouter(tags=["links"])
redirect_router = APIRouter(tags=["redirect"])


def _to_read(link: Link) -> LinkRead:
    data = LinkRead.model_validate(link)
    data.short_url = f"{settings.base_url}/{link.short_code}"
    return data


@api_router.post(
    "/links",
    response_model=LinkRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_internal_token)],
)
async def create_link(
    payload: LinkCreate, session: AsyncSession = Depends(get_session)
) -> LinkRead:
    link = await LinkService(session).create(payload)
    return _to_read(link)


@api_router.get(
    "/links",
    response_model=list[LinkRead],
    dependencies=[Depends(require_internal_token)],
)
async def list_links(
    owner_id: int | None = None, session: AsyncSession = Depends(get_session)
) -> list[LinkRead]:
    stmt = select(Link).order_by(Link.created_at.desc())
    if owner_id is not None:
        stmt = stmt.where(Link.owner_id == owner_id)
    links = (await session.scalars(stmt)).all()
    return [_to_read(link) for link in links]


@api_router.delete(
    "/links/{code}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_internal_token)],
)
async def delete_link(
    code: str,
    session: AsyncSession = Depends(get_session),
    cache: LinkCache = Depends(get_cache),
) -> Response:
    # Remove from the database and purge the hot-cache entry (idempotent).
    await LinkService(session).delete(code)
    await cache.invalidate(code)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ─────────────────────── redirect helpers ───────────────────────


def _hash_ip(ip: str | None) -> str | None:
    """Hash the visitor IP so raw addresses are never stored (privacy)."""
    if not ip:
        return None
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def _build_click_event(code: str, request: Request) -> ClickEvent:
    return ClickEvent(
        short_code=code,
        user_agent=request.headers.get("user-agent"),
        referer=request.headers.get("referer"),
        ip_hash=_hash_ip(_client_ip(request)),
        timestamp=datetime.now(UTC),
    )


def _cache_ttl(link: Link, default_ttl: int) -> int:
    """Cap the cache TTL by the link's remaining lifetime."""
    if link.expires_at is None:
        return default_ttl
    remaining = int((link.expires_at - datetime.now(UTC)).total_seconds())
    return max(1, min(default_ttl, remaining))


@redirect_router.get("/{code}")
async def follow_short_link(
    code: str,
    request: Request,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    cache: LinkCache = Depends(get_cache),
    emit: ClickEmitter = Depends(get_click_emitter),
) -> RedirectResponse:
    # 1) L1 cache lookup.
    target = await cache.get_url(code)

    # 2) On miss, hit the DB (expiry-aware) and warm the cache.
    if target is None:
        link = await LinkService(session).resolve(code)
        if link is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="short link not found or expired",
            )
        target = link.original_url
        await cache.set_url(code, target, _cache_ttl(link, settings.cache_ttl_seconds))

    # 3) Count the click *after* responding — never delays the redirect.
    #    Capture the trace id now; it is gone by the time the task runs.
    background.add_task(emit, _build_click_event(code, request), trace_id_var.get())

    return RedirectResponse(url=target, status_code=REDIRECT_STATUS)
