"""Tests for apps.accounts.backup — the thin R2 wrapper for DB backups."""
from unittest.mock import MagicMock

import pytest

from apps.accounts import backup
from apps.accounts.backup import is_configured


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
    assert is_configured() is False


def test_is_configured_true_when_all_set(set_r2):
    assert is_configured() is True


def test_is_configured_false_when_one_field_missing(settings):
    settings.R2_ENDPOINT_URL = "https://x.r2.cloudflarestorage.com"
    settings.R2_ACCESS_KEY_ID = "k"
    settings.R2_SECRET_ACCESS_KEY = "s"
    settings.R2_BUCKET = ""  # missing
    assert is_configured() is False


def test_upload_backup_calls_s3_with_correct_args(set_r2, monkeypatch, tmp_path):
    src = tmp_path / "test.sqlite3"
    src.write_bytes(b"fake sqlite contents")
    fake_client = MagicMock()
    monkeypatch.setattr(backup, "_client", lambda: fake_client)

    backup.upload_backup(str(src), "db-backups/2026-05-23.sqlite3")

    fake_client.upload_file.assert_called_once_with(
        str(src), "hoa-test-bucket", "db-backups/2026-05-23.sqlite3",
    )


def test_list_backup_keys_returns_keys_under_prefix(set_r2, monkeypatch):
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
    fake_client = MagicMock()
    fake_client.list_objects_v2.return_value = {}  # no Contents key
    monkeypatch.setattr(backup, "_client", lambda: fake_client)

    assert backup.list_backup_keys() == []


def test_delete_backup_calls_s3_delete(set_r2, monkeypatch):
    fake_client = MagicMock()
    monkeypatch.setattr(backup, "_client", lambda: fake_client)

    backup.delete_backup("db-backups/2026-05-21.sqlite3")

    fake_client.delete_object.assert_called_once_with(
        Bucket="hoa-test-bucket", Key="db-backups/2026-05-21.sqlite3",
    )
