"""Snapshot the SQLite DB and upload it to R2 under db-backups/YYYY-MM-DD.sqlite3."""
import datetime as dt
import logging
import os
import re
import sqlite3
import tempfile

from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone

from apps.accounts import backup
from apps.accounts.models import BackupLog

logger = logging.getLogger(__name__)

RETENTION_DAYS = 30
# Matches db-backups/YYYY-MM-DD.sqlite3 — the format produced by this command.
_KEY_DATE_PATTERN = re.compile(
    rf"^{re.escape(backup.BACKUP_PREFIX)}(\d{{4}}-\d{{2}}-\d{{2}})\.sqlite3$",
)


class Command(BaseCommand):
    help = "Snapshot the database and upload it to R2."

    def handle(self, *args, **options):
        today = dt.date.today()
        object_key = f"{backup.BACKUP_PREFIX}{today.isoformat()}.sqlite3"

        log, _ = BackupLog.objects.get_or_create(run_date=today)

        tmp_path = self._snapshot_sqlite()
        try:
            size_bytes = os.path.getsize(tmp_path)
            backup.upload_backup(tmp_path, object_key)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        log.object_key = object_key
        log.bytes_uploaded = size_bytes
        log.finished_at = timezone.now()
        log.save()

        self._prune_old_backups(today)

        self.stdout.write(self.style.SUCCESS(
            f"Backed up {size_bytes} bytes to {object_key}",
        ))

    @staticmethod
    def _snapshot_sqlite() -> str:
        """Use SQLite's online backup API to copy the live DB to a temp file.

        Snapshots through Django's live connection so this works against both
        file-backed databases (production) and the in-memory database that
        pytest-django creates for tests.
        """
        # NamedTemporaryFile(delete=False) so we control unlink ourselves.
        with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as tmp:
            tmp_path = tmp.name
        connection.ensure_connection()
        src = connection.connection
        dst = sqlite3.connect(tmp_path)
        try:
            with dst:
                src.backup(dst)
        finally:
            dst.close()
        return tmp_path

    @staticmethod
    def _prune_old_backups(today: dt.date) -> None:
        """Delete db-backups/* objects whose dated name is > RETENTION_DAYS old.

        Keys not matching the `db-backups/YYYY-MM-DD.sqlite3` shape (a foreign
        README, a typo'd manual upload) are left alone.
        """
        cutoff = today - dt.timedelta(days=RETENTION_DAYS)
        for key in backup.list_backup_keys():
            match = _KEY_DATE_PATTERN.match(key)
            if not match:
                continue
            try:
                key_date = dt.date.fromisoformat(match.group(1))
            except ValueError:
                continue
            if key_date < cutoff:
                backup.delete_backup(key)
