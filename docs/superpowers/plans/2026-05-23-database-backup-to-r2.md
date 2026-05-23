# Database Backup to R2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an automated daily backup of `db.sqlite3` to Cloudflare R2 with 30-day retention, observable via the Account page, and a manual restore runbook — all triggered without a scheduler by middleware on the first web request of each day.

**Architecture:** A `BackupLog` model tracks one row per day, enforcing "first request wins" via a unique `run_date`. A new `BackupMiddleware` (in `apps/accounts/middleware.py`, alongside `TimezoneMiddleware`) checks the log and dispatches the `backup_database` management command if today's backup hasn't run. The command uses Python's `sqlite3.Connection.backup()` API to produce a consistent snapshot (safe under concurrent writes), uploads to R2 via a thin wrapper in `apps/accounts/backup.py` (mirroring the `apps/projects/storage.py` pattern), then prunes objects older than 30 days. All errors are caught at the middleware boundary so a failed backup never breaks a web request — failures are recorded on the `BackupLog` row instead.

**Tech Stack:** Django 5.0.x, Python stdlib `sqlite3`, `boto3` (already a dep), pytest-django, ruff. R2 credentials are already in `config/settings.py` as `R2_ENDPOINT_URL` / `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` / `R2_BUCKET`.

---

## File Structure

**New files:**
- `apps/accounts/backup.py` — thin R2 wrapper exposing `is_configured()`, `upload_backup()`, `list_backup_keys()`, `delete_backup()`. Test seam: monkeypatch these from tests instead of mocking `boto3` directly. Mirrors `apps/projects/storage.py`.
- `apps/accounts/management/__init__.py` — empty package marker.
- `apps/accounts/management/commands/__init__.py` — empty package marker.
- `apps/accounts/management/commands/backup_database.py` — the management command. Does the SQLite snapshot, calls into `backup.py` for upload + prune, returns a `BackupLog`-shaped dict.
- `apps/accounts/migrations/0003_backuplog.py` — auto-generated.
- `apps/accounts/tests/test_backup_command.py` — tests for the management command.
- `apps/accounts/tests/test_backup_middleware.py` — tests for `BackupMiddleware`.
- `docs/runbooks/restore-database.md` — the manual restore runbook.

**Modified files:**
- `apps/accounts/models.py` — add `BackupLog`.
- `apps/accounts/admin.py` — register `BackupLog`.
- `apps/accounts/middleware.py` — add `BackupMiddleware` (`TimezoneMiddleware` stays untouched).
- `apps/accounts/views.py` — pass `latest_backup` to the profile template context.
- `templates/accounts/profile.html` — add a "Last backup" panel.
- `apps/accounts/tests/test_models.py` — `BackupLog` model test.
- `apps/accounts/tests/test_views.py` — Account-page renders the latest-backup panel.
- `config/settings.py` — register `BackupMiddleware`.

---

## Task 1: `BackupLog` model + migration

The foundation. Everything else writes to this table; nothing depends on R2 yet.

**Files:**
- Modify: `apps/accounts/models.py`
- Create: `apps/accounts/migrations/0003_backuplog.py` (auto-generated)
- Test: `apps/accounts/tests/test_models.py`

- [ ] **Step 1: Write the failing test**

Append to `apps/accounts/tests/test_models.py`:

```python
@pytest.mark.django_db
def test_backup_log_run_date_unique():
    from django.db import IntegrityError
    from apps.accounts.models import BackupLog
    import datetime as dt
    BackupLog.objects.create(run_date=dt.date(2026, 5, 23))
    with pytest.raises(IntegrityError):
        BackupLog.objects.create(run_date=dt.date(2026, 5, 23))


@pytest.mark.django_db
def test_backup_log_optional_fields_default_blank():
    from apps.accounts.models import BackupLog
    import datetime as dt
    log = BackupLog.objects.create(run_date=dt.date(2026, 5, 24))
    assert log.finished_at is None
    assert log.bytes_uploaded is None
    assert log.object_key == ""
    assert log.error == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest apps/accounts/tests/test_models.py -v`
Expected: FAIL — `ImportError: cannot import name 'BackupLog' from 'apps.accounts.models'`.

- [ ] **Step 3: Add the `BackupLog` model**

Append to `apps/accounts/models.py`:

```python
class BackupLog(models.Model):
    """One row per day the database backup ran (or attempted to run).

    The unique `run_date` makes the 'first request wins' race in
    BackupMiddleware safe — a second concurrent request raises IntegrityError
    on insert and is treated as a no-op. The remaining fields are
    observability: when did it start/finish, how big was the uploaded file,
    what's its R2 key, and was there an error.
    """

    run_date = models.DateField(unique=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    bytes_uploaded = models.PositiveIntegerField(null=True, blank=True)
    object_key = models.CharField(max_length=200, blank=True)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ["-run_date"]

    def __str__(self):
        status = "ok" if not self.error else "error"
        return f"Backup {self.run_date} ({status})"
```

- [ ] **Step 4: Generate the migration**

Run: `python manage.py makemigrations accounts`
Expected: creates `apps/accounts/migrations/0003_backuplog.py` with one `CreateModel` operation.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest apps/accounts/tests/test_models.py -v`
Expected: PASS — both new tests green plus the existing tests.

- [ ] **Step 6: Commit**

```bash
git add apps/accounts/models.py apps/accounts/migrations/0003_backuplog.py apps/accounts/tests/test_models.py
git commit -m "feat(accounts): BackupLog model with unique run_date"
```

---

## Task 2: `apps/accounts/backup.py` — R2 wrapper module

A thin module that wraps boto3 client construction and the four operations we need (upload, list, delete, configured-check). Tests for callers monkeypatch THESE functions, not boto3 directly. Mirrors the existing `apps/projects/storage.py` pattern.

**Files:**
- Create: `apps/accounts/backup.py`
- Test: `apps/accounts/tests/test_backup.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `apps/accounts/tests/test_backup.py`:

```python
"""Tests for apps.accounts.backup — the thin R2 wrapper for DB backups."""
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def unset_r2(settings):
    """All R2 credentials blank — simulates local dev."""
    settings.R2_ENDPOINT_URL = ""
    settings.R2_ACCESS_KEY_ID = ""
    settings.R2_SECRET_ACCESS_KEY = ""
    settings.R2_BUCKET = ""


@pytest.fixture
def set_r2(settings):
    """All R2 credentials populated — simulates production."""
    settings.R2_ENDPOINT_URL = "https://example.r2.cloudflarestorage.com"
    settings.R2_ACCESS_KEY_ID = "test-key"
    settings.R2_SECRET_ACCESS_KEY = "test-secret"
    settings.R2_BUCKET = "hoa-test-bucket"


def test_is_configured_false_when_any_blank(unset_r2):
    from apps.accounts.backup import is_configured
    assert is_configured() is False


def test_is_configured_true_when_all_set(set_r2):
    from apps.accounts.backup import is_configured
    assert is_configured() is True


def test_is_configured_false_when_one_field_missing(settings):
    settings.R2_ENDPOINT_URL = "https://x.r2.cloudflarestorage.com"
    settings.R2_ACCESS_KEY_ID = "k"
    settings.R2_SECRET_ACCESS_KEY = "s"
    settings.R2_BUCKET = ""  # missing
    from apps.accounts.backup import is_configured
    assert is_configured() is False


def test_upload_backup_calls_s3_with_correct_args(set_r2, monkeypatch, tmp_path):
    from apps.accounts import backup
    src = tmp_path / "test.sqlite3"
    src.write_bytes(b"fake sqlite contents")
    fake_client = MagicMock()
    monkeypatch.setattr(backup, "_client", lambda: fake_client)

    backup.upload_backup(str(src), "db-backups/2026-05-23.sqlite3")

    fake_client.upload_file.assert_called_once_with(
        str(src), "hoa-test-bucket", "db-backups/2026-05-23.sqlite3",
    )


def test_list_backup_keys_returns_keys_under_prefix(set_r2, monkeypatch):
    from apps.accounts import backup
    fake_client = MagicMock()
    fake_client.list_objects_v2.return_value = {
        "Contents": [
            {"Key": "db-backups/2026-05-21.sqlite3"},
            {"Key": "db-backups/2026-05-22.sqlite3"},
            {"Key": "db-backups/2026-05-23.sqlite3"},
        ],
    }
    monkeypatch.setattr(backup, "_client", lambda: fake_client)

    keys = backup.list_backup_keys()

    fake_client.list_objects_v2.assert_called_once_with(
        Bucket="hoa-test-bucket", Prefix="db-backups/",
    )
    assert keys == [
        "db-backups/2026-05-21.sqlite3",
        "db-backups/2026-05-22.sqlite3",
        "db-backups/2026-05-23.sqlite3",
    ]


def test_list_backup_keys_handles_empty_prefix(set_r2, monkeypatch):
    """list_objects_v2 omits 'Contents' entirely when the prefix is empty."""
    from apps.accounts import backup
    fake_client = MagicMock()
    fake_client.list_objects_v2.return_value = {}  # no Contents key
    monkeypatch.setattr(backup, "_client", lambda: fake_client)

    assert backup.list_backup_keys() == []


def test_delete_backup_calls_s3_delete(set_r2, monkeypatch):
    from apps.accounts import backup
    fake_client = MagicMock()
    monkeypatch.setattr(backup, "_client", lambda: fake_client)

    backup.delete_backup("db-backups/2026-05-21.sqlite3")

    fake_client.delete_object.assert_called_once_with(
        Bucket="hoa-test-bucket", Key="db-backups/2026-05-21.sqlite3",
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest apps/accounts/tests/test_backup.py -v`
Expected: FAIL — module `apps.accounts.backup` does not exist.

- [ ] **Step 3: Create the backup module**

Create `apps/accounts/backup.py`:

```python
"""Thin R2 wrapper for database-backup operations.

Mirrors apps/projects/storage.py — a small surface that callers
(BackupMiddleware, backup_database command) can monkeypatch in tests instead
of mocking boto3 directly.
"""
import boto3
from botocore.client import Config
from django.conf import settings

BACKUP_PREFIX = "db-backups/"


def is_configured() -> bool:
    """True iff every R2 credential setting has a non-empty value."""
    return bool(
        settings.R2_ENDPOINT_URL
        and settings.R2_ACCESS_KEY_ID
        and settings.R2_SECRET_ACCESS_KEY
        and settings.R2_BUCKET,
    )


def _client():
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def upload_backup(local_path: str, key: str) -> None:
    """Upload a local file to R2 at the given key."""
    _client().upload_file(local_path, settings.R2_BUCKET, key)


def list_backup_keys() -> list[str]:
    """Return all object keys under the BACKUP_PREFIX, sorted ascending."""
    response = _client().list_objects_v2(
        Bucket=settings.R2_BUCKET, Prefix=BACKUP_PREFIX,
    )
    contents = response.get("Contents", [])
    return sorted(item["Key"] for item in contents)


def delete_backup(key: str) -> None:
    """Delete one R2 object by key."""
    _client().delete_object(Bucket=settings.R2_BUCKET, Key=key)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest apps/accounts/tests/test_backup.py -v`
Expected: PASS — all 7 tests green.

- [ ] **Step 5: Commit**

```bash
git add apps/accounts/backup.py apps/accounts/tests/test_backup.py
git commit -m "feat(accounts): thin R2 wrapper for backup operations"
```

---

## Task 3: `backup_database` management command — happy path

The command that actually does the work: SQLite snapshot via `Connection.backup()`, upload to R2, return a result dict. Pruning comes in Task 4.

**Files:**
- Create: `apps/accounts/management/__init__.py` (empty)
- Create: `apps/accounts/management/commands/__init__.py` (empty)
- Create: `apps/accounts/management/commands/backup_database.py`
- Test: `apps/accounts/tests/test_backup_command.py` (create)

- [ ] **Step 1: Write the failing test**

Create `apps/accounts/tests/test_backup_command.py`:

```python
"""Tests for the backup_database management command."""
import datetime as dt
import sqlite3
from unittest.mock import MagicMock

import pytest
from django.core.management import call_command


@pytest.fixture
def set_r2(settings):
    settings.R2_ENDPOINT_URL = "https://x.r2.cloudflarestorage.com"
    settings.R2_ACCESS_KEY_ID = "k"
    settings.R2_SECRET_ACCESS_KEY = "s"
    settings.R2_BUCKET = "hoa-test"


@pytest.fixture
def stub_backup(monkeypatch):
    """Monkeypatch the apps.accounts.backup functions; return the captures."""
    from apps.accounts import backup
    captured = {"uploads": [], "lists": [], "deletes": []}

    def fake_upload(local_path, key):
        captured["uploads"].append((local_path, key, _file_bytes(local_path)))

    def fake_list():
        captured["lists"].append(True)
        return []

    def fake_delete(key):
        captured["deletes"].append(key)

    monkeypatch.setattr(backup, "upload_backup", fake_upload)
    monkeypatch.setattr(backup, "list_backup_keys", fake_list)
    monkeypatch.setattr(backup, "delete_backup", fake_delete)
    return captured


def _file_bytes(path):
    with open(path, "rb") as f:
        return f.read()


@pytest.mark.django_db
def test_backup_command_uploads_with_dated_key(set_r2, stub_backup):
    call_command("backup_database")
    assert len(stub_backup["uploads"]) == 1
    local_path, key, _data = stub_backup["uploads"][0]
    today = dt.date.today().isoformat()
    assert key == f"db-backups/{today}.sqlite3"


@pytest.mark.django_db
def test_backup_command_produces_valid_sqlite_file(set_r2, stub_backup):
    call_command("backup_database")
    _local_path, _key, data = stub_backup["uploads"][0]
    # The uploaded bytes must open as a valid SQLite database.
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    conn = sqlite3.connect(tmp_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name='accounts_userprofile'",
    )
    assert cursor.fetchone() is not None
    conn.close()


@pytest.mark.django_db
def test_backup_command_creates_backup_log_row(set_r2, stub_backup):
    from apps.accounts.models import BackupLog
    call_command("backup_database")
    log = BackupLog.objects.get(run_date=dt.date.today())
    assert log.error == ""
    assert log.finished_at is not None
    assert log.object_key == f"db-backups/{dt.date.today().isoformat()}.sqlite3"
    assert log.bytes_uploaded is not None and log.bytes_uploaded > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest apps/accounts/tests/test_backup_command.py -v`
Expected: FAIL — `Unknown command: 'backup_database'`.

- [ ] **Step 3: Create the management package**

Create two empty files:
- `apps/accounts/management/__init__.py` (empty file)
- `apps/accounts/management/commands/__init__.py` (empty file)

(These are package markers so Django discovers the command. Both files must exist and be zero-byte / empty.)

- [ ] **Step 4: Create the backup_database command (happy path only)**

Create `apps/accounts/management/commands/backup_database.py`:

```python
"""Snapshot the SQLite DB and upload it to R2 under db-backups/YYYY-MM-DD.sqlite3."""
import datetime as dt
import logging
import os
import sqlite3
import tempfile

from django.conf import settings
from django.core.management.base import BaseCommand
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
        """Use SQLite's online backup API to copy the live DB to a temp file."""
        live_db = str(settings.DATABASES["default"]["NAME"])
        # NamedTemporaryFile(delete=False) so we control unlink ourselves.
        with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as tmp:
            tmp_path = tmp.name
        src = sqlite3.connect(live_db)
        dst = sqlite3.connect(tmp_path)
        try:
            with dst:
                src.backup(dst)
        finally:
            src.close()
            dst.close()
        return tmp_path
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest apps/accounts/tests/test_backup_command.py -v`
Expected: PASS — all 3 tests green.

- [ ] **Step 6: Commit**

```bash
git add apps/accounts/management apps/accounts/management/__init__.py apps/accounts/management/commands/__init__.py apps/accounts/management/commands/backup_database.py apps/accounts/tests/test_backup_command.py
git commit -m "feat(accounts): backup_database command snapshots SQLite to R2"
```

---

## Task 4: Retention — prune backups older than 30 days

Extend the command to delete `db-backups/YYYY-MM-DD.sqlite3` objects whose date is more than 30 days before today. Done after upload so a fresh backup is in place before any deletion.

**Files:**
- Modify: `apps/accounts/management/commands/backup_database.py`
- Test: `apps/accounts/tests/test_backup_command.py`

- [ ] **Step 1: Write the failing tests**

Append to `apps/accounts/tests/test_backup_command.py`:

```python
@pytest.mark.django_db
def test_backup_command_prunes_objects_older_than_30_days(
    set_r2, monkeypatch,
):
    """Given 35 daily backups, the 5 oldest are deleted; 30 newest kept."""
    from apps.accounts import backup
    today = dt.date.today()
    existing_keys = [
        f"{backup.BACKUP_PREFIX}{(today - dt.timedelta(days=offset)).isoformat()}.sqlite3"
        for offset in range(1, 36)  # 35 backups, 1-35 days old
    ]
    deletes = []
    monkeypatch.setattr(backup, "upload_backup", lambda *a: None)
    monkeypatch.setattr(backup, "list_backup_keys", lambda: existing_keys)
    monkeypatch.setattr(backup, "delete_backup", lambda key: deletes.append(key))

    call_command("backup_database")

    # The 5 oldest (31-35 days) must be deleted.
    expected_deleted = {
        f"{backup.BACKUP_PREFIX}{(today - dt.timedelta(days=offset)).isoformat()}.sqlite3"
        for offset in range(31, 36)
    }
    assert set(deletes) == expected_deleted


@pytest.mark.django_db
def test_backup_command_keeps_unparseable_keys(set_r2, monkeypatch):
    """A foreign key under the backup prefix (e.g. README) must NOT be deleted."""
    from apps.accounts import backup
    existing_keys = [
        f"{backup.BACKUP_PREFIX}README.txt",
        f"{backup.BACKUP_PREFIX}not-a-date.sqlite3",
        f"{backup.BACKUP_PREFIX}{(dt.date.today() - dt.timedelta(days=50)).isoformat()}.sqlite3",
    ]
    deletes = []
    monkeypatch.setattr(backup, "upload_backup", lambda *a: None)
    monkeypatch.setattr(backup, "list_backup_keys", lambda: existing_keys)
    monkeypatch.setattr(backup, "delete_backup", lambda key: deletes.append(key))

    call_command("backup_database")

    # Only the parseable, > 30 days old key is deleted.
    assert deletes == [
        f"{backup.BACKUP_PREFIX}{(dt.date.today() - dt.timedelta(days=50)).isoformat()}.sqlite3",
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest apps/accounts/tests/test_backup_command.py::test_backup_command_prunes_objects_older_than_30_days -v`
Expected: FAIL — no `delete_backup` calls are being made.

- [ ] **Step 3: Add the retention logic**

In `apps/accounts/management/commands/backup_database.py`, add a module constant and a helper, then call the helper after the upload. The full updated file:

```python
"""Snapshot the SQLite DB and upload it to R2 under db-backups/YYYY-MM-DD.sqlite3."""
import datetime as dt
import logging
import os
import re
import sqlite3
import tempfile

from django.conf import settings
from django.core.management.base import BaseCommand
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
        """Use SQLite's online backup API to copy the live DB to a temp file."""
        live_db = str(settings.DATABASES["default"]["NAME"])
        with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as tmp:
            tmp_path = tmp.name
        src = sqlite3.connect(live_db)
        dst = sqlite3.connect(tmp_path)
        try:
            with dst:
                src.backup(dst)
        finally:
            src.close()
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest apps/accounts/tests/test_backup_command.py -v`
Expected: PASS — all 5 tests green.

- [ ] **Step 5: Commit**

```bash
git add apps/accounts/management/commands/backup_database.py apps/accounts/tests/test_backup_command.py
git commit -m "feat(accounts): prune backup objects older than 30 days"
```

---

## Task 5: `BackupMiddleware` — daily idempotent trigger

The middleware that fires the management command once per day on the first request, modeled on `RecurringGenerationMiddleware`.

**Files:**
- Modify: `apps/accounts/middleware.py`
- Modify: `config/settings.py`
- Test: `apps/accounts/tests/test_backup_middleware.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `apps/accounts/tests/test_backup_middleware.py`:

```python
"""Tests for BackupMiddleware."""
import datetime as dt

import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from apps.accounts.middleware import BackupMiddleware
from apps.accounts.models import BackupLog


@pytest.fixture
def set_r2(settings):
    settings.R2_ENDPOINT_URL = "https://x.r2.cloudflarestorage.com"
    settings.R2_ACCESS_KEY_ID = "k"
    settings.R2_SECRET_ACCESS_KEY = "s"
    settings.R2_BUCKET = "hoa-test"


def _call_middleware(monkeypatch_command=None):
    """Run the middleware once. Optionally stub call_command to capture calls."""
    calls = []

    def get_response(request):
        return HttpResponse()

    middleware = BackupMiddleware(get_response)
    if monkeypatch_command is not None:
        from apps.accounts import middleware as mw_module
        monkeypatch_command.setattr(
            mw_module, "call_command",
            lambda name, *a, **k: calls.append(name),
        )
    request = RequestFactory().get("/")
    middleware(request)
    return calls


@pytest.mark.django_db
def test_first_call_of_day_runs_backup(set_r2, monkeypatch):
    calls = _call_middleware(monkeypatch_command=monkeypatch)
    assert calls == ["backup_database"]
    assert BackupLog.objects.filter(run_date=dt.date.today()).exists()


@pytest.mark.django_db
def test_second_call_same_day_does_not_run(set_r2, monkeypatch):
    BackupLog.objects.create(run_date=dt.date.today())
    calls = _call_middleware(monkeypatch_command=monkeypatch)
    assert calls == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest apps/accounts/tests/test_backup_middleware.py -v`
Expected: FAIL — `ImportError: cannot import name 'BackupMiddleware' from 'apps.accounts.middleware'`.

- [ ] **Step 3: Add `BackupMiddleware`**

Append to `apps/accounts/middleware.py` (the existing `TimezoneMiddleware` stays untouched):

```python
import datetime as dt
import logging

from django.core.management import call_command

from apps.accounts.models import BackupLog

backup_logger = logging.getLogger(__name__)


class BackupMiddleware:
    """Runs the database backup once per day, lazily.

    PythonAnywhere's free tier has no scheduled tasks, so the backup is
    triggered by the first web request of each day. The unique constraint
    on BackupLog.run_date makes 'first request wins' race-safe.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self._maybe_backup()
        return self.get_response(request)

    @staticmethod
    def _maybe_backup():
        today = dt.date.today()
        # get_or_create races on the unique run_date — the second caller's
        # IntegrityError surfaces as `created=False` so only one path runs
        # the actual backup.
        _, created = BackupLog.objects.get_or_create(run_date=today)
        if not created:
            return
        try:
            call_command("backup_database")
        except Exception:  # noqa: BLE001 - never let backup break a request
            backup_logger.exception("Database backup failed")
```

The two existing imports at the top of `middleware.py` (`zoneinfo`, `from django.utils import timezone`) stay where they are. The new imports (`datetime as dt`, `logging`, `call_command`, `BackupLog`) sit in their own block underneath.

- [ ] **Step 4: Register the middleware in settings**

In `config/settings.py`, the existing MIDDLEWARE list has `TimezoneMiddleware` registered after `AuthenticationMiddleware`. Add `BackupMiddleware` immediately after it:

```python
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.accounts.middleware.TimezoneMiddleware",
    "apps.accounts.middleware.BackupMiddleware",
    "apps.projects.middleware.RecurringGenerationMiddleware",
    "apps.projects.middleware.ActorMiddleware",
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest apps/accounts/tests/test_backup_middleware.py -v`
Expected: PASS — both tests green.

- [ ] **Step 6: Commit**

```bash
git add apps/accounts/middleware.py config/settings.py apps/accounts/tests/test_backup_middleware.py
git commit -m "feat(accounts): BackupMiddleware fires backup once per day"
```

---

## Task 6: Local-dev safety — skip when R2 unconfigured

When R2 credentials aren't set (local dev), the command must not crash trying to make a boto3 call. It writes a `BackupLog` row with an explanatory `error` field and exits cleanly. The middleware in turn relies on that row's `created` flag to skip subsequent same-day calls.

**Files:**
- Modify: `apps/accounts/management/commands/backup_database.py`
- Test: `apps/accounts/tests/test_backup_command.py`

- [ ] **Step 1: Write the failing test**

Append to `apps/accounts/tests/test_backup_command.py`:

```python
@pytest.fixture
def unset_r2(settings):
    settings.R2_ENDPOINT_URL = ""
    settings.R2_ACCESS_KEY_ID = ""
    settings.R2_SECRET_ACCESS_KEY = ""
    settings.R2_BUCKET = ""


@pytest.mark.django_db
def test_backup_command_skips_gracefully_when_r2_unconfigured(
    unset_r2, monkeypatch,
):
    """In local dev R2 creds are blank; the command must skip without
    crashing and record an explanatory message on the BackupLog row."""
    from apps.accounts import backup
    from apps.accounts.models import BackupLog
    uploads = []
    monkeypatch.setattr(backup, "upload_backup", lambda *a: uploads.append(a))

    call_command("backup_database")

    assert uploads == []  # no upload attempted
    log = BackupLog.objects.get(run_date=dt.date.today())
    assert "not configured" in log.error.lower()
    assert log.finished_at is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest apps/accounts/tests/test_backup_command.py::test_backup_command_skips_gracefully_when_r2_unconfigured -v`
Expected: FAIL — the command tries to call `boto3.client(...)` with empty creds and raises (or attempts a real call).

- [ ] **Step 3: Add the configured-check guard**

In `apps/accounts/management/commands/backup_database.py`, update the `handle` method to short-circuit when R2 is unconfigured. The full updated method:

```python
    def handle(self, *args, **options):
        today = dt.date.today()
        log, _ = BackupLog.objects.get_or_create(run_date=today)

        if not backup.is_configured():
            log.error = "R2 not configured; backup skipped"
            log.finished_at = timezone.now()
            log.save()
            self.stdout.write(self.style.WARNING(
                "R2 not configured; backup skipped.",
            ))
            return

        object_key = f"{backup.BACKUP_PREFIX}{today.isoformat()}.sqlite3"
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest apps/accounts/tests/test_backup_command.py -v`
Expected: PASS — all 6 tests green (the existing 5 plus the new one).

- [ ] **Step 5: Commit**

```bash
git add apps/accounts/management/commands/backup_database.py apps/accounts/tests/test_backup_command.py
git commit -m "feat(accounts): backup skips cleanly when R2 unconfigured"
```

---

## Task 7: Error capture — R2 failures never break the request

If R2 raises mid-upload (network blip, auth error), the command should catch it, write the exception text to `BackupLog.error` (truncated), and not propagate. The middleware already has its own outer try/except, but capturing the error on the log row is what makes it visible to operators.

**Files:**
- Modify: `apps/accounts/management/commands/backup_database.py`
- Test: `apps/accounts/tests/test_backup_command.py`

- [ ] **Step 1: Write the failing test**

Append to `apps/accounts/tests/test_backup_command.py`:

```python
@pytest.mark.django_db
def test_backup_command_records_error_when_upload_fails(set_r2, monkeypatch):
    """If upload_backup raises, the exception text lands on BackupLog.error
    and the command exits cleanly (does not propagate)."""
    from apps.accounts import backup
    from apps.accounts.models import BackupLog

    def boom(*args, **kwargs):
        raise RuntimeError("R2 unreachable: simulated outage")

    monkeypatch.setattr(backup, "upload_backup", boom)
    monkeypatch.setattr(backup, "list_backup_keys", lambda: [])
    monkeypatch.setattr(backup, "delete_backup", lambda key: None)

    call_command("backup_database")  # must NOT raise

    log = BackupLog.objects.get(run_date=dt.date.today())
    assert "R2 unreachable" in log.error
    assert log.finished_at is not None


@pytest.mark.django_db
def test_backup_command_truncates_error_to_2000_chars(set_r2, monkeypatch):
    from apps.accounts import backup
    from apps.accounts.models import BackupLog

    def boom(*args, **kwargs):
        raise RuntimeError("X" * 5000)

    monkeypatch.setattr(backup, "upload_backup", boom)

    call_command("backup_database")

    log = BackupLog.objects.get(run_date=dt.date.today())
    assert len(log.error) <= 2000
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest apps/accounts/tests/test_backup_command.py -v -k "records_error or truncates"`
Expected: FAIL — the exception propagates out of `call_command`.

- [ ] **Step 3: Add the try/except around the upload**

In `apps/accounts/management/commands/backup_database.py`, update the body of `handle` (after the unconfigured short-circuit) to wrap the snapshot/upload section. The full updated `handle`:

```python
    def handle(self, *args, **options):
        today = dt.date.today()
        log, _ = BackupLog.objects.get_or_create(run_date=today)

        if not backup.is_configured():
            log.error = "R2 not configured; backup skipped"
            log.finished_at = timezone.now()
            log.save()
            self.stdout.write(self.style.WARNING(
                "R2 not configured; backup skipped.",
            ))
            return

        object_key = f"{backup.BACKUP_PREFIX}{today.isoformat()}.sqlite3"
        size_bytes: int | None = None
        try:
            tmp_path = self._snapshot_sqlite()
            try:
                size_bytes = os.path.getsize(tmp_path)
                backup.upload_backup(tmp_path, object_key)
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            self._prune_old_backups(today)
        except Exception as exc:  # noqa: BLE001
            log.error = str(exc)[:2000]
            log.finished_at = timezone.now()
            log.save()
            self.stdout.write(self.style.ERROR(f"Backup failed: {exc}"))
            return

        log.object_key = object_key
        log.bytes_uploaded = size_bytes
        log.finished_at = timezone.now()
        log.save()

        self.stdout.write(self.style.SUCCESS(
            f"Backed up {size_bytes} bytes to {object_key}",
        ))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest apps/accounts/tests/test_backup_command.py -v`
Expected: PASS — all 8 tests green.

- [ ] **Step 5: Commit**

```bash
git add apps/accounts/management/commands/backup_database.py apps/accounts/tests/test_backup_command.py
git commit -m "feat(accounts): capture R2 errors on BackupLog, never raise"
```

---

## Task 8: Admin registration + Account-page "Last backup" panel

The smallest observability surface — `BackupLog` in the Django admin, and one panel on the Account page showing the latest row's status, size, and timestamp.

**Files:**
- Modify: `apps/accounts/admin.py`
- Modify: `apps/accounts/views.py`
- Modify: `templates/accounts/profile.html`
- Test: `apps/accounts/tests/test_views.py`

- [ ] **Step 1: Write the failing test**

Append to `apps/accounts/tests/test_views.py`:

```python
@pytest.mark.django_db
def test_profile_page_shows_latest_backup(client):
    import datetime as dt
    from django.utils import timezone
    from apps.accounts.models import BackupLog
    User = get_user_model()
    user = User.objects.create_user(
        username="kim@example.com", email="kim@example.com",
        password="Sufficiently-Long-Pw-1",
    )
    BackupLog.objects.create(
        run_date=dt.date.today(),
        finished_at=timezone.now(),
        bytes_uploaded=12345,
        object_key="db-backups/" + dt.date.today().isoformat() + ".sqlite3",
    )
    client.force_login(user)
    response = client.get(reverse("accounts:profile"))
    content = response.content.decode()
    assert "Last backup" in content
    assert dt.date.today().isoformat() in content


@pytest.mark.django_db
def test_profile_page_shows_no_backup_yet_when_none(client):
    User = get_user_model()
    user = User.objects.create_user(
        username="leo@example.com", email="leo@example.com",
        password="Sufficiently-Long-Pw-1",
    )
    client.force_login(user)
    response = client.get(reverse("accounts:profile"))
    content = response.content.decode()
    assert "No backups yet" in content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest apps/accounts/tests/test_views.py -v -k "backup or no_backup"`
Expected: FAIL — the profile page doesn't render any backup-related content.

- [ ] **Step 3: Register the model in admin**

Replace the full contents of `apps/accounts/admin.py` with:

```python
from django.contrib import admin

from .models import BackupLog, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "timezone", "updated_at")
    search_fields = ("user__username", "user__email")


@admin.register(BackupLog)
class BackupLogAdmin(admin.ModelAdmin):
    list_display = ("run_date", "finished_at", "bytes_uploaded", "object_key", "error")
    readonly_fields = (
        "run_date", "started_at", "finished_at", "bytes_uploaded", "object_key", "error",
    )
    ordering = ("-run_date",)
```

- [ ] **Step 4: Pass `latest_backup` to the profile context**

Replace the full contents of `apps/accounts/views.py` with:

```python
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import ProfileForm
from .models import BackupLog


@login_required
def profile(request):
    profile_obj = request.user.profile
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=profile_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect("accounts:profile")
    else:
        form = ProfileForm(instance=profile_obj)
    return render(request, "accounts/profile.html", {
        "form": form,
        "profile": profile_obj,
        "latest_backup": BackupLog.objects.order_by("-run_date").first(),
    })
```

- [ ] **Step 5: Add the "Last backup" panel to the template**

In `templates/accounts/profile.html`, the file currently ends with the Change-password / Manage-categories button row inside the main `<div class="bg-white rounded-lg shadow p-6 max-w-md">` card. Add a new `<section>` immediately after that closing `</div>` (the card's), and before `{% endblock %}`:

```html
<section class="bg-white rounded-lg shadow p-6 max-w-md mt-6">
  <h2 class="text-sm font-semibold text-gray-500 uppercase mb-3">Last backup</h2>
  {% if latest_backup %}
    <dl class="space-y-2 text-sm">
      <div class="flex"><dt class="w-32 text-gray-500">Date</dt>
        <dd class="text-gray-900">{{ latest_backup.run_date }}</dd></div>
      <div class="flex"><dt class="w-32 text-gray-500">Finished</dt>
        <dd class="text-gray-900">
          {% if latest_backup.finished_at %}{{ latest_backup.finished_at|date:"M j · g:i A" }}{% else %}—{% endif %}
        </dd></div>
      <div class="flex"><dt class="w-32 text-gray-500">Size</dt>
        <dd class="text-gray-900">
          {% if latest_backup.bytes_uploaded %}{{ latest_backup.bytes_uploaded }} bytes{% else %}—{% endif %}
        </dd></div>
      <div class="flex"><dt class="w-32 text-gray-500">Status</dt>
        <dd class="{% if latest_backup.error %}text-red-700{% else %}text-green-700{% endif %}">
          {% if latest_backup.error %}{{ latest_backup.error }}{% else %}OK{% endif %}
        </dd></div>
    </dl>
  {% else %}
    <p class="text-gray-400 text-sm">No backups yet — the first one will run on tomorrow's first web request.</p>
  {% endif %}
</section>
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest apps/accounts/tests/test_views.py -v`
Expected: PASS — both new tests green, existing tests still green.

- [ ] **Step 7: Commit**

```bash
git add apps/accounts/admin.py apps/accounts/views.py templates/accounts/profile.html apps/accounts/tests/test_views.py
git commit -m "feat(accounts): show latest backup on Account page and admin"
```

---

## Task 9: Restore runbook

A markdown runbook checked into the repo so the procedure is versioned and visible to anyone with access to the source.

**Files:**
- Create: `docs/runbooks/restore-database.md`

- [ ] **Step 1: Write the runbook**

Create `docs/runbooks/restore-database.md`:

````markdown
# Restoring the database from an R2 backup

The HOA Task Manager backs up `db.sqlite3` to R2 daily under
`db-backups/YYYY-MM-DD.sqlite3` (30-day retention). This runbook walks
through restoring from one of those backups.

**Do this when:** the live DB is corrupted, missing, or has bad data that
needs to be rolled back to a prior day's state.

**Estimated time:** 10 minutes.

---

## 1. Pick which backup to restore

In the [Cloudflare R2 dashboard](https://dash.cloudflare.com), open the
HOA Task Manager bucket → `db-backups/`. Each object is a daily snapshot
named `YYYY-MM-DD.sqlite3`. Pick the most recent one that predates the
problem you're recovering from.

(Alternative: in the PythonAnywhere Bash console,
`python manage.py shell -c "from apps.accounts.backup import list_backup_keys; print('\n'.join(list_backup_keys()))"`
will print the list.)

## 2. Download the chosen file

In the R2 dashboard, click the object's row → **Download**. Save it
locally. Don't rename it.

## 3. Upload to PythonAnywhere

On the PythonAnywhere **Files** tab, navigate to `/home/CICA/HOA-Task-Manager/`.
Click **Upload a file** and select the `.sqlite3` you downloaded.

## 4. Replace the live DB

In the PythonAnywhere Bash console:

```bash
cd ~/HOA-Task-Manager

# ALWAYS back up the current DB first — in case the restore is wrong.
cp db.sqlite3 "db.sqlite3.PRE-RESTORE-$(date -u +%Y%m%dT%H%M%SZ)"

# Replace. Use the actual filename you uploaded.
mv 2026-05-23.sqlite3 db.sqlite3
```

## 5. Reload the web app

On the PythonAnywhere **Web** tab, click **Reload cica.pythonanywhere.com**.

## 6. Verify

Open the app in your browser and confirm:
- You can log in.
- The Projects list shows the data you expect for the restored date.
- The Dashboard activity feed shows activity up to the restore date.

## 7. Clean up

Once you've confirmed the restore is good, delete the `PRE-RESTORE-*` file
in the next backup window (give it a couple of days first in case you
need to undo the restore):

```bash
cd ~/HOA-Task-Manager
ls -la db.sqlite3.PRE-RESTORE-*
rm db.sqlite3.PRE-RESTORE-<timestamp>   # only after you're sure
```

---

## Troubleshooting

- **"OperationalError: database is locked" after restore.** Reload the
  Web tab again — a stale connection can hold the old file open.
- **App loads but shows the wrong data.** Double-check the date of the
  file you uploaded. The filename is the snapshot's date in UTC.
- **R2 dashboard doesn't show recent backups.** Check the Account page —
  the "Last backup" panel will show when the most recent attempt ran and
  whether it errored.

## Notes

- **Backups roll daily at the first web request after UTC midnight.** If
  you need a backup of the current moment (not just yesterday's snapshot),
  run `python manage.py backup_database` from the Bash console first.
- **The PRE-RESTORE file is your safety net.** Keep it for at least one
  business day in case the restore turns out to be the wrong choice.
````

- [ ] **Step 2: Verify it renders**

The runbook is pure markdown — no test needed beyond a manual eyeball. Open it in your editor's markdown preview (or on GitHub) and confirm it reads cleanly.

- [ ] **Step 3: Commit**

```bash
git add docs/runbooks/restore-database.md
git commit -m "docs: restore-from-R2 runbook"
```

---

## Task 10: Final pass — full suite, lint, deploy notes

A safety belt before merging: full test suite green, lint clean, no leftover unused files. No Tailwind rebuild needed — the only new template content uses utility classes that are already in `output.css` (`mt-6`, `space-y-2`, `text-red-700`, `text-green-700`, etc., all of which appear elsewhere).

**Files:** none

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest -q`
Expected: PASS — the existing tests plus the ~15 new ones from this plan. Total around 209 tests.

- [ ] **Step 2: Run the linter**

Run: `ruff check .`
Expected: "All checks passed!"

- [ ] **Step 3: Verify the Tailwind bundle**

Spot-check that the classes used by the new Account-page panel are present in `static/css/output.css`. They should be, because they're all utilities already used elsewhere. Run:

```bash
grep -oE '\.mt-6\{|\.space-y-2\{|\.text-red-700\{|\.text-green-700\{' static/css/output.css | sort -u
```

Expected: all four classes appear at least once. If any are missing, run:

```bash
./bin/tailwindcss.exe -i static/css/input.css -o static/css/output.css --minify
git add static/css/output.css
git commit -m "build: rebuild Tailwind CSS for last-backup panel"
```

Otherwise, no commit needed.

- [ ] **Step 4: Final commit (only if Tailwind was rebuilt above)**

Already handled in Step 3 if needed.

---

## Self-Review

**1. Spec coverage** (checking each section of `2026-05-23-database-backup-to-r2-design.md`):
- §2 Scope: in-scope items (daily backup, 30-day retention, manual command, runbook, tests) → Tasks 1-9. Out-of-scope items (R2 attachment backup, encryption, automated restore, off-cloud destinations) → explicitly not built. ✓
- §3 Architecture: `BackupMiddleware` → Task 5. `BackupLog` model → Task 1. `backup_database` command → Tasks 3, 4, 6, 7. `_prune_old_backups` → Task 4. Local-dev safety → Task 6. ✓
- §4 Data model: `BackupLog(run_date unique, started_at, finished_at, bytes_uploaded, object_key, error)` → Task 1 verbatim. Migration `0003_backuplog.py` → Task 1 Step 4. ✓
- §5 Storage layout: `db-backups/YYYY-MM-DD.sqlite3` → Task 3, `_KEY_DATE_PATTERN` validates the exact shape in Task 4. ✓
- §6 Restore procedure: 7 numbered steps in spec → 7-step runbook in Task 9 plus troubleshooting + notes. ✓
- §7 Error handling: R2 creds missing → Task 6. R2 upload fails → Task 7. SQLite backup fails → same try/except in Task 7. Pruning fails → currently no separate try/except, but pruning happens inside the broader try/except in Task 7 so a prune exception is captured the same way. Two requests racing → covered by the `created=False` branch in Task 5. ✓
- §8 Observability: `BackupLog` in admin → Task 8 Step 3. Account-page "Last backup" panel → Task 8 Steps 4-5. ✓
- §9 Testing: all six bullets mapped to tests across Tasks 1-8. ✓
- §10 Security: `BackupLog.error` truncated to 2000 chars → Task 7 Step 3. HTTPS via boto3 default → Task 2 Step 3 (uses `endpoint_url`). ✓
- §11 Cost / §12 / §13: not implementation tasks; spec text. ✓

**2. Placeholder scan:** No "TBD", "TODO", "fill in details", "similar to Task N", "implement appropriate error handling", or descriptions without code. Every code step shows the exact code.

**3. Type consistency:**
- `BackupLog` field names (`run_date`, `started_at`, `finished_at`, `bytes_uploaded`, `object_key`, `error`) used consistently across Task 1 (definition), Task 3 (writing), Task 6 (error field), Task 7 (error field truncation), Task 8 (admin list, template rendering).
- `BACKUP_PREFIX` constant — defined in Task 2 (`apps/accounts/backup.py`), referenced in Task 3 (object_key), Task 4 (`_KEY_DATE_PATTERN`), and the runbook in Task 9 (path mentioned).
- `RETENTION_DAYS = 30` — defined in Task 4, no other consumer.
- `is_configured()` — defined in Task 2, called in Task 6.
- `upload_backup(local_path, key)` / `list_backup_keys()` / `delete_backup(key)` — signatures defined in Task 2, called in Tasks 3, 4, 7 with matching argument shape.

One self-correction: Task 4's `_prune_old_backups(today)` is staticmethod-decorated and takes `today` as an explicit arg. Verified consistent in Task 4 Step 3 and the eventual `handle` body in Task 6 (`self._prune_old_backups(today)`). No drift.
