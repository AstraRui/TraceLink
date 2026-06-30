"""Stats-service application entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.core.config import settings
from app.core.logging import (
    LogStopper,
    TraceMiddleware,
    setup_console_logging,
    start_db_logging,
)
from app.db.session import engine

setup_console_logging("stats")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    stop_logging: LogStopper = await start_db_logging(engine, "stats")
    try:
        yield
    finally:
        await stop_logging()


app = FastAPI(
    title="Stats Service",
    version="0.1.0",
    description="Ingests click events and serves aggregated click statistics.",
    # Serve docs under the gateway prefix without touching real route paths.
    docs_url=f"{settings.docs_prefix}/docs",
    openapi_url=f"{settings.docs_prefix}/openapi.json",
    redoc_url=None,
    lifespan=lifespan,
)
app.add_middleware(TraceMiddleware, service="stats")


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(router, prefix="/api")
