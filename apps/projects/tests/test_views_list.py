import datetime as dt

import pytest
from django.urls import reverse

from apps.projects.models import Project, ProjectStatus


@pytest.mark.django_db
def test_list_excludes_completed_by_default(auth_client, user, category):
    Project.objects.create(title="Active", category=category, created_by=user)
    Project.objects.create(
        title="DoneOne", category=category, created_by=user,
        status=ProjectStatus.COMPLETED,
    )
    response = auth_client.get(reverse("projects:list"))
    assert response.status_code == 200
    assert b"Active" in response.content
    assert b"DoneOne" not in response.content


@pytest.mark.django_db
def test_list_excludes_templates(auth_client, user, category):
    Project.objects.create(title="Plain", category=category, created_by=user)
    Project.objects.create(
        title="Template", category=category, created_by=user,
        is_recurring_template=True,
    )
    response = auth_client.get(reverse("projects:list"))
    assert b"Plain" in response.content
    assert b"Template" not in response.content


@pytest.mark.django_db
def test_list_status_filter(auth_client, user, category):
    Project.objects.create(title="A", category=category, created_by=user)
    Project.objects.create(
        title="B", category=category, created_by=user,
        status=ProjectStatus.IN_PROGRESS,
    )
    response = auth_client.get(reverse("projects:list") + "?status=in_progress")
    assert b">A<" not in response.content  # project title "A" not in table cell
    assert b">B<" in response.content


@pytest.mark.django_db
def test_list_search_by_title(auth_client, user, category):
    Project.objects.create(title="Sprinkler", category=category, created_by=user)
    Project.objects.create(title="Concrete", category=category, created_by=user)
    response = auth_client.get(reverse("projects:list") + "?q=spr")
    assert b"Sprinkler" in response.content
    assert b"Concrete" not in response.content


@pytest.mark.django_db
def test_list_sort_by_due_date(auth_client, user, category):
    today = dt.date.today()
    Project.objects.create(
        title="Later", category=category, created_by=user,
        projected_completion_date=today + dt.timedelta(days=20),
    )
    Project.objects.create(
        title="Sooner", category=category, created_by=user,
        projected_completion_date=today + dt.timedelta(days=5),
    )
    response = auth_client.get(reverse("projects:list") + "?sort=due")
    body = response.content.decode()
    assert body.index("Sooner") < body.index("Later")


@pytest.mark.django_db
def test_list_show_completed(auth_client, user, category):
    Project.objects.create(
        title="DoneOne", category=category, created_by=user,
        status=ProjectStatus.COMPLETED,
    )
    response = auth_client.get(reverse("projects:list") + "?show_completed=1")
    assert b"DoneOne" in response.content


@pytest.mark.django_db
def test_list_empty_state(auth_client):
    response = auth_client.get(reverse("projects:list"))
    assert response.status_code == 200
    assert b"No projects yet" in response.content
