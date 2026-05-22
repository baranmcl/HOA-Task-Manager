import pytest
from django.urls import reverse

from apps.projects.models import ProjectStatus


@pytest.mark.django_db
def test_detail_renders(auth_client, project):
    response = auth_client.get(reverse("projects:detail", args=[project.pk]))
    assert response.status_code == 200
    assert project.title.encode() in response.content


@pytest.mark.django_db
def test_detail_shows_delay_banner(auth_client, project):
    project.status = ProjectStatus.DELAYED
    project.delay_reason = "Vendor is on vacation"
    project.save()
    response = auth_client.get(reverse("projects:detail", args=[project.pk]))
    assert b"Delayed" in response.content
    assert b"Vendor is on vacation" in response.content


@pytest.mark.django_db
def test_detail_404_for_missing(auth_client):
    response = auth_client.get(reverse("projects:detail", args=[999999]))
    assert response.status_code == 404
