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
