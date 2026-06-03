#!/bin/sh
# App-machine entrypoint: run migrations (the /data volume is mounted here,
# unlike Fly's release_command machine), then hand off to gunicorn.
set -e

# One-shot restore-from-R2: if RESTORE_FROM_R2_KEY is set, pull that object
# from the R2 bucket and overwrite /data/db.sqlite3 before migrations run.
# Useful for disaster recovery and for the initial seed when SSH/SFTP into
# the volume isn't available. Unset RESTORE_FROM_R2_KEY after a successful
# restore — otherwise every machine restart will re-overwrite the DB.
if [ -n "$RESTORE_FROM_R2_KEY" ]; then
  echo "[entrypoint] Restoring /data/db.sqlite3 from R2 key: $RESTORE_FROM_R2_KEY"
  uv run python -c "import boto3, os; boto3.client('s3', endpoint_url=os.environ['R2_ENDPOINT_URL'], aws_access_key_id=os.environ['R2_ACCESS_KEY_ID'], aws_secret_access_key=os.environ['R2_SECRET_ACCESS_KEY']).download_file(os.environ['R2_BUCKET'], os.environ['RESTORE_FROM_R2_KEY'], '/data/db.sqlite3')"
  echo "[entrypoint] Restore complete. Unset RESTORE_FROM_R2_KEY to prevent re-restore on next start."
fi

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
