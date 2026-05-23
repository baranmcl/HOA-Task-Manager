"""Snapshot the SQLite DB and upload it to R2 under db-backups/YYYY-MM-DD.sqlite3."""
import datetime as dt
import logging
import os
import sqlite3
import tempfile

from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone

from apps.accounts import backup
from apps.accounts.models import BackupLog

logger = logging.getLogger(__name__)


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
