#!/bin/sh
# App-machine entrypoint: run migrations (the /data volume is mounted here,
# unlike Fly's release_command machine), then hand off to gunicorn.
set -e

uv run python manage.py migrate --noinput

# One-time superuser bootstrap. createsuperuser --noinput reads
# DJANGO_SUPERUSER_USERNAME / _EMAIL / _PASSWORD from the environment.
# Guarded so it is a no-op once those secrets are removed; `|| true`
# keeps boot going if the user already exists on a later restart.
if [ -n "$DJANGO_SUPERUSER_USERNAME" ]; then
  uv run python manage.py createsuperuser --noinput 2>&1 || true
fi

exec uv run gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 2 \
  --access-logfile -
