import datetime as dt

import pytest
from django.urls import reverse

from apps.projects.models import (
    Project,
    ProjectStatus,
    RACIAssignment,
    RACIRole,
)
from apps.roster.models import RosterPerson


@pytest.mark.django_db
def test_board_requires_login(client):
    response = client.get(reverse("projects:board"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_board_default_renders_three_columns(auth_client, user, category):
    Project.objects.create(
        title="A", category=category, created_by=user,
        status=ProjectStatus.NOT_STARTED,
    )
    response = auth_client.get(reverse("projects:board"))
    assert response.status_code == 200
    columns = response.context["columns"]
    labels = [c["label"] for c in columns]
    assert labels == ["Not started", "In progress", "Delayed"]


@pytest.mark.django_db
def test_board_show_completed_adds_fourth_column(auth_client):
    response = auth_client.get(reverse("projects:board") + "?show_completed=1")
    columns = response.context["columns"]
    labels = [c["label"] for c in columns]
    assert labels == ["Not started", "In progress", "Delayed", "Completed"]


@pytest.mark.django_db
def test_board_completed_project_hidden_by_default(auth_client, user, category):
    Project.objects.create(
        title="Done thing", category=category, created_by=user,
        status=ProjectStatus.COMPLETED,
    )
    response = auth_client.get(reverse("projects:board"))
    assert "Done thing" not in response.content.decode()


@pytest.mark.django_db
def test_board_places_projects_in_correct_columns(auth_client, user, category):
    Project.objects.create(
        title="Not yet", category=category, created_by=user,
        status=ProjectStatus.NOT_STARTED,
    )
    Project.objects.create(
        title="Working", category=category, created_by=user,
        status=ProjectStatus.IN_PROGRESS,
    )
    Project.objects.create(
        title="Stuck", category=category, created_by=user,
        status=ProjectStatus.DELAYED, delay_reason="vendor backed out",
    )
    response = auth_client.get(reverse("projects:board"))
    by_status = {c["status"]: [p.title for p in c["cards"]] for c in response.context["columns"]}
    assert by_status[ProjectStatus.NOT_STARTED] == ["Not yet"]
    assert by_status[ProjectStatus.IN_PROGRESS] == ["Working"]
    assert by_status[ProjectStatus.DELAYED] == ["Stuck"]


@pytest.mark.django_db
def test_board_excludes_recurring_templates(auth_client, user, category):
    Project.objects.create(
        title="Template only", category=category, created_by=user,
        status=ProjectStatus.NOT_STARTED,
        is_recurring_template=True, recurrence_rule="monthly",
        next_due_date=dt.date(2026, 6, 1),
    )
    response = auth_client.get(reverse("projects:board"))
    assert "Template only" not in response.content.decode()


@pytest.mark.django_db
def test_board_person_filter_scopes_cards(auth_client, user, category):
    mike = RosterPerson.objects.create(name="Mike Smith")
    laurel = RosterPerson.objects.create(name="Laurel Baran")
    mikes = Project.objects.create(
        title="Mike task", category=category, created_by=user,
        status=ProjectStatus.IN_PROGRESS,
    )
    RACIAssignment.objects.create(project=mikes, person=mike, role=RACIRole.RESPONSIBLE)
    laurels = Project.objects.create(
        title="Laurel task", category=category, created_by=user,
        status=ProjectStatus.IN_PROGRESS,
    )
    RACIAssignment.objects.create(project=laurels, person=laurel, role=RACIRole.RESPONSIBLE)

    response = auth_client.get(reverse("projects:board") + f"?person={mike.pk}")
    content = response.content.decode()
    assert "Mike task" in content
    assert "Laurel task" not in content


@pytest.mark.django_db
def test_board_default_shows_all_people(auth_client, user, category):
    mike = RosterPerson.objects.create(name="Mike Smith")
    laurel = RosterPerson.objects.create(name="Laurel Baran")
    p1 = Project.objects.create(
        title="Mike task", category=category, created_by=user,
        status=ProjectStatus.IN_PROGRESS,
    )
    RACIAssignment.objects.create(project=p1, person=mike, role=RACIRole.RESPONSIBLE)
    p2 = Project.objects.create(
        title="Laurel task", category=category, created_by=user,
        status=ProjectStatus.IN_PROGRESS,
    )
    RACIAssignment.objects.create(project=p2, person=laurel, role=RACIRole.RESPONSIBLE)

    response = auth_client.get(reverse("projects:board"))
    content = response.content.decode()
    assert "Mike task" in content
    assert "Laurel task" in content


@pytest.mark.django_db
def test_board_cards_sorted_by_due_date_within_column(auth_client, user, category):
    Project.objects.create(
        title="Later", category=category, created_by=user,
        status=ProjectStatus.IN_PROGRESS,
        projected_completion_date=dt.date(2026, 9, 1),
    )
    Project.objects.create(
        title="Sooner", category=category, created_by=user,
        status=ProjectStatus.IN_PROGRESS,
        projected_completion_date=dt.date(2026, 6, 1),
    )
    Project.objects.create(
        title="No date", category=category, created_by=user,
        status=ProjectStatus.IN_PROGRESS,
        projected_completion_date=None,
    )
    response = auth_client.get(reverse("projects:board"))
    in_progress = [c for c in response.context["columns"]
                   if c["status"] == ProjectStatus.IN_PROGRESS][0]
    titles = [p.title for p in in_progress["cards"]]
    assert titles == ["Sooner", "Later", "No date"]


@pytest.mark.django_db
def test_sidebar_includes_board_link(auth_client):
    response = auth_client.get(reverse("home"))
    content = response.content.decode()
    assert ">Board<" in content
    assert reverse("projects:board") in content
