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
