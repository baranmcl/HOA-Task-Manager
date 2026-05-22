import pytest
from django.urls import reverse

from apps.projects.models import UpdateNote


@pytest.mark.django_db
def test_add_note(auth_client, project):
    response = auth_client.post(
        reverse("projects:note_add", args=[project.pk]),
        {"body": "Met with vendor."},
    )
    assert response.status_code == 200
    assert UpdateNote.objects.filter(project=project, body="Met with vendor.").exists()


@pytest.mark.django_db
def test_add_empty_note_rejected(auth_client, project):
    response = auth_client.post(
        reverse("projects:note_add", args=[project.pk]),
        {"body": "  "},
    )
    assert response.status_code == 400
