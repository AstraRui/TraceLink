# ─────────────────────────────────────────────────────────────
# Stage 1 — build the Tailwind CSS bundle.
# The 39 MB standalone Tailwind binary and the raw sources stay in this
# stage only; the final image keeps just the compiled output.css.
# (debian-slim is glibc-based, which the Tailwind standalone binary needs.)
# ─────────────────────────────────────────────────────────────
FROM debian:bookworm-slim AS css-builder

WORKDIR /build

ADD https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.17/tailwindcss-linux-x64 \
    /usr/local/bin/tailwindcss
RUN chmod +x /usr/local/bin/tailwindcss

COPY tailwind.config.js ./
COPY templates ./templates
COPY static/src ./static/src

RUN tailwindcss -i ./static/src/input.css -o ./output.css --minify


# ─────────────────────────────────────────────────────────────
# Stage 2 — runtime image (Python only, no Node, no Tailwind binary).
# ─────────────────────────────────────────────────────────────
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

WORKDIR /app

RUN pip install --no-cache-dir uv

# Dependencies first for layer caching (prod deps only, no dev).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Application code, templates and static assets (vendored htmx/Chart.js live here).
COPY app ./app
COPY templates ./templates
COPY static ./static
COPY alembic.ini ./
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

# Pull in only the compiled CSS from the build stage.
COPY --from=css-builder /build/output.css ./static/css/output.css

EXPOSE 8000
ENTRYPOINT ["./docker-entrypoint.sh"]
