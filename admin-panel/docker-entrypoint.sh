#!/bin/sh
# Apply DB migrations (creates the users table + bootstrap happens on startup),
# then start the server. docker-compose waits for Postgres to be healthy first.
set -e

uv run alembic upgrade head
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
