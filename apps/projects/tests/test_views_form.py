import pytest
from django.urls import reverse

from apps.projects.models import Project


@pytest.mark.django_db
def test_create_get_renders(auth_client, category):
    response = auth_client.get(reverse("projects:create"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_create_post_creates_project(auth_client, category):
    response = auth_client.post(reverse("projects:create"), {
        "title": "New Project",
        "category": category.pk,
        "status": "not_started",
        "priority": "medium",
        "description": "",
        "tags_text": "",
    })
    assert response.status_code == 302
    assert Project.objects.filter(title="New Project").exists()


@pytest.mark.django_db
def test_edit_post_updates(auth_client, project):
    response = auth_client.post(reverse("projects:edit", args=[project.pk]), {
        "title": "Renamed",
        "category": project.category_id,
        "status": "not_started",
        "priority": "high",
        "description": "",
        "tags_text": "",
    })
    assert response.status_code == 302
    project.refresh_from_db()
    assert project.title == "Renamed"
    assert project.priority == "high"
