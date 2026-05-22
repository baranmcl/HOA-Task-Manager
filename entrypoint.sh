#!/bin/sh
# App-machine entrypoint: run migrations (the /data volume is mounted here,
# unlike Fly's release_command machine), then hand off to gunicorn.
set -e

uv run python manage.py migrate --noinput

exec uv run gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 2 \
  --access-logfile -
