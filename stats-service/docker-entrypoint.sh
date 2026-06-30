#!/bin/sh
# Apply DB migrations, then start the API server.
# (docker-compose waits for Postgres to be healthy before this runs.)
set -e

uv run alembic upgrade head
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
