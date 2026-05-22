import pytest
from django.urls import reverse

from apps.projects.models import Project


@pytest.mark.django_db
def test_category_list_requires_login(client):
    response = client.get(reverse("projects:category_list"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_category_list_renders(auth_client, category):
    response = auth_client.get(reverse("projects:category_list"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_category_list_shows_project_counts(auth_client, category, user):
    Project.objects.create(title="P1", category=category, created_by=user)
    Project.objects.create(title="P2", category=category, created_by=user)
    response = auth_client.get(reverse("projects:category_list"))
    row = next(c for c in response.context["categories"] if c.pk == category.pk)
    assert row.project_count == 2
