import secrets
from pathlib import Path

import boto3
from botocore.client import Config
from django.conf import settings

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

PER_FILE_LIMIT = 10 * 1024 * 1024
PER_PROJECT_LIMIT = 50 * 1024 * 1024


class AttachmentValidationError(Exception):
    pass


def build_object_key(project_id: int, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    token = secrets.token_hex(8)
    return f"projects/{project_id}/{token}{ext}"


def validate_upload(
    *, filename: str, content_type: str, size_bytes: int, project_total: int,
) -> None:
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise AttachmentValidationError(
            f"Files of type {content_type} are not allowed. "
            "Allowed: PDF, JPG, PNG, DOCX, XLSX."
        )
    if size_bytes > PER_FILE_LIMIT:
        raise AttachmentValidationError(
            "File exceeds 10 MB per-file limit."
        )
    if project_total + size_bytes > PER_PROJECT_LIMIT:
        raise AttachmentValidationError(
            "Adding this file would exceed the 50 MB project total."
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


def upload_fileobj(fileobj, key: str, content_type: str) -> None:
    _client().upload_fileobj(
        Fileobj=fileobj,
        Bucket=settings.R2_BUCKET,
        Key=key,
        ExtraArgs={"ContentType": content_type},
    )


def signed_download_url(key: str, *, filename: str, expires_in: int = 300) -> str:
    return _client().generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.R2_BUCKET,
            "Key": key,
            "ResponseContentDisposition": f'attachment; filename="{filename}"',
        },
        ExpiresIn=expires_in,
    )


def delete_object(key: str) -> None:
    _client().delete_object(Bucket=settings.R2_BUCKET, Key=key)
