"""Structured logging with a per-request trace id.

Every record is tagged with the service name, level and the current request's
trace id (``X-Request-ID``), and is shipped asynchronously to the shared
``system_logs`` table in Postgres — giving simple end-to-end tracing across the
microservices and powering the admin Logs viewer.
"""

from __future__ import annotations

import asyncio
import contextvars
import logging
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

# Current request's trace id; "-" outside any request.
trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="-")

LogItem = dict[str, str]

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS system_logs (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    service VARCHAR(32) NOT NULL,
    level VARCHAR(16) NOT NULL,
    trace_id VARCHAR(64),
    logger VARCHAR(128),
    message TEXT NOT NULL
)
"""
_CREATE_INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_system_logs_created_at ON system_logs (created_at)",
    "CREATE INDEX IF NOT EXISTS ix_system_logs_service ON system_logs (service)",
    "CREATE INDEX IF NOT EXISTS ix_system_logs_trace_id ON system_logs (trace_id)",
)


class TraceFilter(logging.Filter):
    """Attach the trace id + service name to every record."""

    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = trace_id_var.get()
        record.service = self.service
        return True


class _QueueHandler(logging.Handler):
    def __init__(self, queue: asyncio.Queue[LogItem | None]) -> None:
        super().__init__()
        self.queue = queue

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.queue.put_nowait(
                {
                    "service": str(getattr(record, "service", "?")),
                    "level": record.levelname,
                    "trace_id": str(getattr(record, "trace_id", "-")),
                    "logger": record.name,
                    "message": record.getMessage(),
                }
            )
        except Exception:
            pass  # logging must never break the app (e.g. queue full)


def setup_console_logging(service: str, level: int = logging.INFO) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    handler = logging.StreamHandler()
    handler.addFilter(TraceFilter(service))
    handler.setFormatter(
        logging.Formatter("[%(service)s] %(levelname)s trace=%(trace_id)s %(name)s: %(message)s")
    )
    root.addHandler(handler)


async def _consume(engine: AsyncEngine, queue: asyncio.Queue[LogItem | None]) -> None:
    insert = text(
        "INSERT INTO system_logs (service, level, trace_id, logger, message) "
        "VALUES (:service, :level, :trace_id, :logger, :message)"
    )
    while True:
        item = await queue.get()
        try:
            if item is None:
                return
            async with engine.begin() as conn:
                await conn.execute(insert, item)
        except Exception:
            pass
        finally:
            queue.task_done()


class LogStopper:
    """Awaitable returned by start_db_logging; call it to flush and stop."""

    def __init__(self, queue: asyncio.Queue[LogItem | None], task: asyncio.Task[None]) -> None:
        self._queue = queue
        self._task = task

    async def __call__(self) -> None:
        await self._queue.put(None)
        await self._task


async def start_db_logging(engine: AsyncEngine, service: str) -> LogStopper:
    async with engine.begin() as conn:
        await conn.execute(text(_CREATE_TABLE))
        for ddl in _CREATE_INDEXES:
            await conn.execute(text(ddl))

    queue: asyncio.Queue[LogItem | None] = asyncio.Queue(maxsize=2000)
    handler = _QueueHandler(queue)
    handler.addFilter(TraceFilter(service))
    handler.setLevel(logging.INFO)
    logging.getLogger().addHandler(handler)
    task = asyncio.create_task(_consume(engine, queue))
    return LogStopper(queue, task)


class TraceMiddleware(BaseHTTPMiddleware):
    """Bind X-Request-ID (or a fresh uuid) to the request; log one access line."""

    def __init__(self, app: ASGIApp, service: str) -> None:
        super().__init__(app)
        self._log = logging.getLogger(f"{service}.access")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        trace = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = trace_id_var.set(trace)
        try:
            response = await call_next(request)
            if request.url.path != "/health":
                self._log.info(
                    "%s %s -> %s", request.method, request.url.path, response.status_code
                )
            response.headers["X-Request-ID"] = trace
            return response
        except Exception:
            self._log.exception("unhandled error on %s %s", request.method, request.url.path)
            raise
        finally:
            trace_id_var.reset(token)
