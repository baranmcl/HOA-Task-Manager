"""Tests for the backup_database management command."""
import datetime as dt
import sqlite3
import tempfile

import pytest
from django.core.management import call_command

from apps.accounts import backup
from apps.accounts.models import BackupLog


@pytest.fixture
def set_r2(settings):
    settings.R2_ENDPOINT_URL = "https://x.r2.cloudflarestorage.com"
    settings.R2_ACCESS_KEY_ID = "k"
    settings.R2_SECRET_ACCESS_KEY = "s"
    settings.R2_BUCKET = "hoa-test"


@pytest.fixture
def stub_backup(monkeypatch):
    """Monkeypatch the apps.accounts.backup functions; return the captures."""
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


@pytest.mark.django_db(transaction=True)
def test_backup_command_uploads_with_dated_key(set_r2, stub_backup):
    call_command("backup_database")
    assert len(stub_backup["uploads"]) == 1
    _local_path, key, _data = stub_backup["uploads"][0]
    today = dt.date.today().isoformat()
    assert key == f"db-backups/{today}.sqlite3"


@pytest.mark.django_db(transaction=True)
def test_backup_command_produces_valid_sqlite_file(set_r2, stub_backup):
    call_command("backup_database")
    _local_path, _key, data = stub_backup["uploads"][0]
    # The uploaded bytes must open as a valid SQLite database.
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


@pytest.mark.django_db(transaction=True)
def test_backup_command_creates_backup_log_row(set_r2, stub_backup):
    call_command("backup_database")
    log = BackupLog.objects.get(run_date=dt.date.today())
    assert log.error == ""
    assert log.finished_at is not None
    assert log.object_key == f"db-backups/{dt.date.today().isoformat()}.sqlite3"
    assert log.bytes_uploaded is not None and log.bytes_uploaded > 0


@pytest.mark.django_db(transaction=True)
def test_backup_command_prunes_objects_older_than_30_days(
    set_r2, monkeypatch,
):
    """Given 35 daily backups, the 5 oldest are deleted; 30 newest kept."""
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


@pytest.mark.django_db(transaction=True)
def test_backup_command_keeps_unparseable_keys(set_r2, monkeypatch):
    """A foreign key under the backup prefix (e.g. README) must NOT be deleted."""
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


@pytest.fixture
def unset_r2(settings):
    settings.R2_ENDPOINT_URL = ""
    settings.R2_ACCESS_KEY_ID = ""
    settings.R2_SECRET_ACCESS_KEY = ""
    settings.R2_BUCKET = ""


@pytest.mark.django_db(transaction=True)
def test_backup_command_skips_gracefully_when_r2_unconfigured(
    unset_r2, monkeypatch,
):
    """In local dev R2 creds are blank; the command must skip without
    crashing and record an explanatory message on the BackupLog row."""
    uploads = []
    monkeypatch.setattr(backup, "upload_backup", lambda *a: uploads.append(a))

    call_command("backup_database")

    assert uploads == []  # no upload attempted
    log = BackupLog.objects.get(run_date=dt.date.today())
    assert "not configured" in log.error.lower()
    assert log.finished_at is not None
