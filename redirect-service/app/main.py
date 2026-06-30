"""Redirect-service application entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import api_router, redirect_router
from app.core.config import settings
from app.core.logging import (
    LogStopper,
    TraceMiddleware,
    setup_console_logging,
    start_db_logging,
)
from app.db.session import engine

setup_console_logging("redirect")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    stop_logging: LogStopper = await start_db_logging(engine, "redirect")
    try:
        yield
    finally:
        await stop_logging()


app = FastAPI(
    title="Redirect Service",
    version="0.1.0",
    description="Creates short links and redirects visitors to the original URL.",
    # Serve docs under the gateway prefix without touching real route paths.
    docs_url=f"{settings.docs_prefix}/docs",
    openapi_url=f"{settings.docs_prefix}/openapi.json",
    redoc_url=None,
    lifespan=lifespan,
)
app.add_middleware(TraceMiddleware, service="redirect")


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


# API first; the catch-all redirect router ("/{code}") is registered last so it
# never shadows /health, /docs, /openapi.json or /api/*.
app.include_router(api_router, prefix="/api")
app.include_router(redirect_router)
