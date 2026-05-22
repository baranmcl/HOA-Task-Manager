import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.projects.models import Attachment


@pytest.fixture(autouse=True)
def stub_r2(monkeypatch):
    """Replace R2 calls with no-ops so tests don't need network."""
    from apps.projects import storage
    monkeypatch.setattr(storage, "upload_fileobj", lambda *a, **k: None)
    monkeypatch.setattr(storage, "delete_object", lambda key: None)
    monkeypatch.setattr(storage, "signed_download_url",
        lambda key, *, filename, expires_in=300: f"https://example.com/{key}")


@pytest.mark.django_db
def test_upload_pdf(auth_client, project):
    f = SimpleUploadedFile("quote.pdf", b"%PDF-1.4 ...", content_type="application/pdf")
    response = auth_client.post(
        reverse("projects:attachment_upload", args=[project.pk]),
        {"file": f},
    )
    assert response.status_code == 200
    assert Attachment.objects.filter(project=project, original_filename="quote.pdf").exists()


@pytest.mark.django_db
def test_upload_disallowed_type_rejected(auth_client, project):
    f = SimpleUploadedFile("script.exe", b"bin", content_type="application/x-msdownload")
    response = auth_client.post(
        reverse("projects:attachment_upload", args=[project.pk]),
        {"file": f},
    )
    assert response.status_code == 400
    assert b"not allowed" in response.content


@pytest.mark.django_db
def test_upload_too_large_rejected(auth_client, project, monkeypatch):
    from apps.projects import storage
    monkeypatch.setattr(storage, "PER_FILE_LIMIT", 100)
    f = SimpleUploadedFile("big.pdf", b"x" * 200, content_type="application/pdf")
    response = auth_client.post(
        reverse("projects:attachment_upload", args=[project.pk]),
        {"file": f},
    )
    assert response.status_code == 400
    assert b"10 MB" in response.content or b"per-file" in response.content


@pytest.mark.django_db
def test_delete_attachment(auth_client, project, user):
    a = Attachment.objects.create(
        project=project, file_key="x", original_filename="x.pdf",
        content_type="application/pdf", size_bytes=100, uploaded_by=user,
    )
    response = auth_client.post(reverse("projects:attachment_delete", args=[a.pk]))
    assert response.status_code == 200
    assert not Attachment.objects.filter(pk=a.pk).exists()


@pytest.mark.django_db
def test_download_redirects_to_signed_url(auth_client, project, user):
    a = Attachment.objects.create(
        project=project, file_key="key123", original_filename="x.pdf",
        content_type="application/pdf", size_bytes=100, uploaded_by=user,
    )
    response = auth_client.get(reverse("projects:attachment_download", args=[a.pk]))
    assert response.status_code == 302
    assert "key123" in response.url
