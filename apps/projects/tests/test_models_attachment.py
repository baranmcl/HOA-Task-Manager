import pytest

from apps.projects.models import Attachment


@pytest.mark.django_db
def test_create_attachment(project, user):
    a = Attachment.objects.create(
        project=project,
        file_key="projects/1/abc123.pdf",
        original_filename="quote.pdf",
        content_type="application/pdf",
        size_bytes=120_000,
        uploaded_by=user,
    )
    assert a.original_filename == "quote.pdf"
    assert str(a) == "quote.pdf"


@pytest.mark.django_db
def test_attachment_human_size(project, user):
    a = Attachment.objects.create(
        project=project, file_key="x", original_filename="x", content_type="application/pdf",
        size_bytes=1_500_000, uploaded_by=user,
    )
    assert a.human_size == "1.5 MB"


@pytest.mark.django_db
def test_project_attachment_total_bytes(project, user):
    Attachment.objects.create(
        project=project, file_key="x1", original_filename="a", content_type="application/pdf",
        size_bytes=1_000_000, uploaded_by=user,
    )
    Attachment.objects.create(
        project=project, file_key="x2", original_filename="b", content_type="application/pdf",
        size_bytes=2_000_000, uploaded_by=user,
    )
    assert Attachment.total_bytes_for_project(project) == 3_000_000
