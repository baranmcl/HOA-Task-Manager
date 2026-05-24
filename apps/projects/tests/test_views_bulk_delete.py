import pytest
from django.urls import reverse

from apps.projects.models import ActivityLog, Project, ProjectStatus


@pytest.mark.django_db
def test_bulk_delete_requires_login(client):
    response = client.post(reverse("projects:bulk_delete"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_bulk_delete_happy_path(auth_client, user, category):
    p1 = Project.objects.create(title="Doomed 1", category=category, created_by=user)
    p2 = Project.objects.create(title="Doomed 2", category=category, created_by=user)
    keeper = Project.objects.create(title="Keeper", category=category, created_by=user)

    response = auth_client.post(
        reverse("projects:bulk_delete"),
        {"ids": [str(p1.pk), str(p2.pk)], "confirm": "delete"},
    )
    assert response.status_code == 302
    assert not Project.objects.filter(pk=p1.pk).exists()
    assert not Project.objects.filter(pk=p2.pk).exists()
    assert Project.objects.filter(pk=keeper.pk).exists()
    assert ActivityLog.objects.filter(verb="deleted project").count() == 2


@pytest.mark.django_db
def test_bulk_delete_without_confirm_word_returns_400(auth_client, user, category):
    p = Project.objects.create(title="Safe", category=category, created_by=user)
    response = auth_client.post(
        reverse("projects:bulk_delete"),
        {"ids": [str(p.pk)], "confirm": "yes"},
    )
    assert response.status_code == 400
    assert Project.objects.filter(pk=p.pk).exists()


@pytest.mark.django_db
def test_bulk_delete_with_no_ids_redirects_back(auth_client):
    response = auth_client.post(
        reverse("projects:bulk_delete"),
        {"confirm": "delete"},
    )
    assert response.status_code == 302


@pytest.mark.django_db
def test_bulk_delete_get_not_allowed(auth_client):
    response = auth_client.get(reverse("projects:bulk_delete"))
    assert response.status_code == 405


@pytest.mark.django_db
def test_list_page_renders_checkboxes(auth_client, user, category):
    Project.objects.create(
        title="A project", category=category, created_by=user,
        status=ProjectStatus.IN_PROGRESS,
    )
    response = auth_client.get(reverse("projects:list"))
    content = response.content.decode()
    assert 'name="ids"' in content
    assert "Delete selected" in content
