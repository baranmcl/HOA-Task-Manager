import pytest

from apps.projects.storage import AttachmentValidationError, build_object_key, validate_upload


def test_build_object_key_includes_project_id():
    key = build_object_key(project_id=42, filename="quote.pdf")
    assert key.startswith("projects/42/")
    assert key.endswith(".pdf")


def test_build_object_key_unique_per_call():
    a = build_object_key(project_id=1, filename="x.pdf")
    b = build_object_key(project_id=1, filename="x.pdf")
    assert a != b


def test_validate_upload_size_limit():
    with pytest.raises(AttachmentValidationError, match="exceeds 10 MB"):
        validate_upload(filename="x.pdf", content_type="application/pdf",
                        size_bytes=11 * 1024 * 1024, project_total=0)


def test_validate_upload_project_limit():
    with pytest.raises(AttachmentValidationError, match="50 MB project"):
        validate_upload(filename="x.pdf", content_type="application/pdf",
                        size_bytes=1_000_000,
                        project_total=50 * 1024 * 1024)


def test_validate_upload_disallowed_type():
    with pytest.raises(AttachmentValidationError, match="not allowed"):
        validate_upload(filename="x.exe", content_type="application/x-msdownload",
                        size_bytes=1000, project_total=0)


def test_validate_upload_allowed_types():
    for ct in [
        "application/pdf",
        "image/jpeg",
        "image/png",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ]:
        validate_upload(filename="x", content_type=ct, size_bytes=100, project_total=0)
