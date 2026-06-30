"""Read access to the shared ``system_logs`` table for the Logs viewer."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

SERVICES = ("admin", "redirect", "stats")
LEVELS = ("INFO", "WARNING", "ERROR")
_MAX_LIMIT = 500


@dataclass
class LogRow:
    created_at: datetime
    service: str
    level: str
    trace_id: str
    logger: str
    message: str


def normalize_service(value: str | None) -> str | None:
    return value if value in SERVICES else None


def normalize_level(value: str | None) -> str | None:
    return value if value in LEVELS else None


class LogReader:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def fetch(
        self,
        service: str | None = None,
        level: str | None = None,
        limit: int = 200,
    ) -> list[LogRow]:
        conditions: list[str] = []
        params: dict[str, object] = {"limit": min(limit, _MAX_LIMIT)}
        if service:
            conditions.append("service = :service")
            params["service"] = service
        if level:
            conditions.append("level = :level")
            params["level"] = level

        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = (
            "SELECT created_at, service, level, trace_id, logger, message "
            f"FROM system_logs{where} ORDER BY id DESC LIMIT :limit"
        )
        result = await self.session.execute(text(sql), params)
        return [
            LogRow(
                created_at=row["created_at"],
                service=row["service"],
                level=row["level"],
                trace_id=row["trace_id"] or "-",
                logger=row["logger"] or "",
                message=row["message"],
            )
            for row in result.mappings().all()
        ]
