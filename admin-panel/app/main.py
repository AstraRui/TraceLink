"""Admin-panel application entrypoint."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.auth import NotAuthenticatedError
from app.core.logging import (
    TraceMiddleware,
    setup_console_logging,
    start_db_logging,
)
from app.db.session import AsyncSessionLocal, engine
from app.services.bootstrap import ensure_admin_user
from app.services.redirect_client import RedirectClient
from app.services.stats_client import StatsClient

setup_console_logging("admin")
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Start log shipping, ensure the first admin exists, open downstream clients.
    stop_logging = await start_db_logging(engine, "admin")
    async with AsyncSessionLocal() as session:
        await ensure_admin_user(session)
    app.state.redirect_client = RedirectClient.create()
    app.state.stats_client = StatsClient.create()
    try:
        yield
    finally:
        await app.state.redirect_client.aclose()
        await app.state.stats_client.aclose()
        await stop_logging()


app = FastAPI(title="Admin Panel", version="0.1.0", lifespan=lifespan)
app.add_middleware(TraceMiddleware, service="admin")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(router)


@app.exception_handler(NotAuthenticatedError)
async def not_authenticated_handler(
    request: Request, exc: NotAuthenticatedError
) -> RedirectResponse:
    # Log every unauthorized access attempt — useful for security monitoring.
    client = request.client.host if request.client else "?"
    logger.warning("unauthorized access to %s from %s", request.url.path, client)
    return RedirectResponse(url="/login", status_code=303)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
