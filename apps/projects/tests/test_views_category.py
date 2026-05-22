import pytest
from django.urls import reverse

from apps.projects.models import Project, ProjectCategory


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


@pytest.mark.django_db
def test_category_add_creates(auth_client):
    response = auth_client.post(reverse("projects:category_add"), {"name": "Landscaping"})
    assert response.status_code == 302
    assert ProjectCategory.objects.filter(name="Landscaping").exists()


@pytest.mark.django_db
def test_category_add_sets_next_display_order(auth_client, category):
    # the `category` fixture has display_order=1
    auth_client.post(reverse("projects:category_add"), {"name": "Landscaping"})
    new = ProjectCategory.objects.get(name="Landscaping")
    assert new.display_order == 2


@pytest.mark.django_db
def test_category_add_rejects_blank(auth_client):
    response = auth_client.post(reverse("projects:category_add"), {"name": ""})
    assert response.status_code == 200
    assert response.context["add_form"].errors
    assert ProjectCategory.objects.filter(name="").count() == 0


@pytest.mark.django_db
def test_category_add_rejects_duplicate(auth_client, category):
    response = auth_client.post(reverse("projects:category_add"), {"name": category.name})
    assert response.status_code == 200
    assert response.context["add_form"].errors
    assert ProjectCategory.objects.filter(name=category.name).count() == 1


@pytest.mark.django_db
def test_category_rename(auth_client, category):
    response = auth_client.post(
        reverse("projects:category_rename", args=[category.pk]),
        {"name": "Capital Projects"},
    )
    assert response.status_code == 302
    category.refresh_from_db()
    assert category.name == "Capital Projects"


@pytest.mark.django_db
def test_category_rename_rejects_blank(auth_client, category):
    auth_client.post(
        reverse("projects:category_rename", args=[category.pk]),
        {"name": "   "},
    )
    category.refresh_from_db()
    assert category.name == "Capital"


@pytest.mark.django_db
def test_category_rename_rejects_duplicate(auth_client, category):
    other = ProjectCategory.objects.create(name="Operational", display_order=2)
    auth_client.post(
        reverse("projects:category_rename", args=[other.pk]),
        {"name": "Capital"},
    )
    other.refresh_from_db()
    assert other.name == "Operational"
