"""Server-rendered routes: authentication, dashboard, link creation."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Form, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.core.templates import templates
from app.db.session import get_session
from app.models.user import User
from app.services.health import HealthChecker
from app.services.logs import LogReader, normalize_level, normalize_service
from app.services.qr import generate_qr_data_uri
from app.services.redirect_client import RedirectClient
from app.services.stats_client import StatsClient

logger = logging.getLogger(__name__)
router = APIRouter()


# ─────────────────────── dependencies / helpers ───────────────────────


def get_redirect_client(request: Request) -> RedirectClient:
    client: RedirectClient = request.app.state.redirect_client
    return client


def get_stats_client(request: Request) -> StatsClient:
    client: StatsClient = request.app.state.stats_client
    return client


def get_health_checker(session: AsyncSession = Depends(get_session)) -> HealthChecker:
    return HealthChecker(session)


def get_log_reader(session: AsyncSession = Depends(get_session)) -> LogReader:
    return LogReader(session)


def _client_host(request: Request) -> str:
    return request.client.host if request.client else "?"


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.jwt_expire_minutes * 60,
    )


def _link_view(link: dict[str, Any]) -> dict[str, Any]:
    # Build the public short URL strictly from BASE_URL (.env), not hardcoded.
    short_url = f"{settings.base_url}/{link['short_code']}"
    return {**link, "short_url": short_url, "qr": generate_qr_data_uri(short_url)}


def _parse_ttl(raw: str | None) -> int | None:
    if raw is None or not raw.strip():
        return None
    return int(raw)  # ValueError handled by the caller


_EMPTY_STATS: dict[str, Any] = {
    "total_clicks": 0,
    "clicks_by_day": [],
    "top_links": [],
    "devices": [],
    "browsers": [],
    "operating_systems": [],
}


async def _load_summary(
    stats_client: StatsClient, short_code: str | None = None, days: int = 30
) -> dict[str, Any]:
    try:
        return await stats_client.get_summary(short_code=short_code, days=days)
    except httpx.HTTPError:
        logger.warning("stats-service unavailable; serving empty stats")
        return dict(_EMPTY_STATS)


# ─────────────────────────── auth ───────────────────────────


@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request) -> Response:
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    session: AsyncSession = Depends(get_session),
) -> Response:
    user = await session.scalar(select(User).where(User.username == username))
    if user is None or not verify_password(password, user.hashed_password):
        logger.warning("failed login attempt username=%r from %s", username, _client_host(request))
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Invalid username or password"},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    _set_session_cookie(response, create_access_token(user.username))
    return response


@router.post("/logout")
async def logout() -> Response:
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(settings.cookie_name)
    return response


# ───────────────────────── dashboard ─────────────────────────


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    user: User = Depends(get_current_user),
    redirect_client: RedirectClient = Depends(get_redirect_client),
    stats_client: StatsClient = Depends(get_stats_client),
) -> Response:
    links = await redirect_client.list_links(user.id)
    link_views = [_link_view(link) for link in links]
    stats = await _load_summary(stats_client)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "user": user,
            "links": link_views,
            "stats": stats,
            "base_url": settings.base_url,
        },
    )


@router.get("/partials/stats", response_class=HTMLResponse)
async def stats_fragment(
    request: Request,
    user: User = Depends(get_current_user),
    stats_client: StatsClient = Depends(get_stats_client),
) -> Response:
    """htmx polling target (HTML) — used for the initial server-side render."""
    stats = await _load_summary(stats_client)
    return templates.TemplateResponse(request, "partials/stats.html", {"stats": stats})


@router.get("/partials/stats.json")
async def stats_json(
    user: User = Depends(get_current_user),
    stats_client: StatsClient = Depends(get_stats_client),
) -> JSONResponse:
    """JSON stats for the live poller; charts update in place via chart.update()."""
    return JSONResponse(await _load_summary(stats_client))


@router.get("/partials/health", response_class=HTMLResponse)
async def health_panel(
    request: Request,
    user: User = Depends(get_current_user),
    checker: HealthChecker = Depends(get_health_checker),
) -> Response:
    """htmx polling target: live status of Postgres, Redis, Redirect & Stats."""
    components = await checker.gather()
    return templates.TemplateResponse(request, "partials/health.html", {"components": components})


@router.get("/logs", response_class=HTMLResponse)
async def logs_page(
    request: Request,
    service: str = "all",
    level: str = "all",
    user: User = Depends(get_current_user),
    reader: LogReader = Depends(get_log_reader),
) -> Response:
    rows = await reader.fetch(normalize_service(service), normalize_level(level))
    return templates.TemplateResponse(
        request, "logs.html", {"rows": rows, "service": service, "level": level}
    )


@router.get("/partials/logs", response_class=HTMLResponse)
async def logs_rows(
    request: Request,
    service: str = "all",
    level: str = "all",
    user: User = Depends(get_current_user),
    reader: LogReader = Depends(get_log_reader),
) -> Response:
    rows = await reader.fetch(normalize_service(service), normalize_level(level))
    return templates.TemplateResponse(request, "partials/logs_rows.html", {"rows": rows})


@router.post("/links", response_class=HTMLResponse)
async def create_link(
    request: Request,
    original_url: str = Form(...),
    ttl_days: str | None = Form(default=None),
    is_private: str | None = Form(default=None),
    user: User = Depends(get_current_user),
    redirect_client: RedirectClient = Depends(get_redirect_client),
) -> Response:
    try:
        ttl = _parse_ttl(ttl_days)
    except ValueError:
        return _error_fragment(request, "Expiry must be a whole number of days.")

    try:
        link = await redirect_client.create_link(
            original_url=original_url,
            owner_id=user.id,
            is_private=bool(is_private),
            ttl_days=ttl,
        )
    except httpx.HTTPStatusError as exc:
        logger.info("link creation rejected: %s", exc)
        return _error_fragment(request, "Could not create link. Check the URL.")

    return templates.TemplateResponse(
        request,
        "partials/link_card.html",
        {"link": _link_view(link), "base_url": settings.base_url},
    )


@router.delete("/links/{code}", response_class=HTMLResponse)
async def delete_link(
    code: str,
    user: User = Depends(get_current_user),
    redirect_client: RedirectClient = Depends(get_redirect_client),
    stats_client: StatsClient = Depends(get_stats_client),
) -> Response:
    """Cascade delete: link (DB + Redis) on redirect-service, then its clicks."""
    await redirect_client.delete_link(code)
    await stats_client.delete_clicks(code)
    return HTMLResponse("")  # empty body → htmx removes the card


@router.get("/links/{code}", response_class=HTMLResponse)
async def link_detail(
    request: Request,
    code: str,
    user: User = Depends(get_current_user),
    redirect_client: RedirectClient = Depends(get_redirect_client),
    stats_client: StatsClient = Depends(get_stats_client),
) -> Response:
    links = await redirect_client.list_links(user.id)
    match = next((link for link in links if link["short_code"] == code), None)
    if match is None:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    stats = await _load_summary(stats_client, short_code=code)
    return templates.TemplateResponse(
        request,
        "detail.html",
        {"link": _link_view(match), "stats": stats, "base_url": settings.base_url},
    )


def _error_fragment(request: Request, message: str) -> Response:
    return templates.TemplateResponse(
        request,
        "partials/link_error.html",
        {"message": message},
        status_code=status.HTTP_400_BAD_REQUEST,
    )
