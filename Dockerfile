# syntax=docker/dockerfile:1.7

# --- Stage 1: build CSS ---
FROM debian:bookworm-slim AS css
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && rm -rf /var/lib/apt/lists/*
RUN curl -sLo /usr/local/bin/tailwindcss \
    https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.4/tailwindcss-linux-x64 \
    && chmod +x /usr/local/bin/tailwindcss
COPY tailwind.config.js ./
COPY templates/ ./templates/
COPY apps/ ./apps/
COPY static/css/input.css ./static/css/input.css
RUN tailwindcss -i ./static/css/input.css -o ./static/css/output.css --minify

# --- Stage 2: python runtime ---
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 UV_COMPILE_BYTECODE=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libsqlite3-0 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install python deps
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy app source
COPY manage.py ./
COPY config/ ./config/
COPY apps/ ./apps/
COPY templates/ ./templates/
COPY static/ ./static/
COPY --from=css /app/static/css/output.css ./static/css/output.css

# Collect static at build time
RUN DJANGO_SECRET_KEY=build-only DJANGO_DEBUG=False DJANGO_ALLOWED_HOSTS=* \
    uv run python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["uv", "run", "gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-"]
