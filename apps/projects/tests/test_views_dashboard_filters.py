import datetime as dt

import pytest
from django.urls import reverse

from apps.projects.models import (
    ActivityLog,
    Project,
    ProjectStatus,
    RACIAssignment,
    RACIRole,
)
from apps.roster.models import RosterPerson


@pytest.fixture
def mike(db):
    return RosterPerson.objects.create(name="Mike Smith")


@pytest.fixture
def laurel(db):
    return RosterPerson.objects.create(name="Laurel Baran")


@pytest.fixture
def linked_user(db, mike):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    u = User.objects.create_user(
        username="linked@example.com", email="linked@example.com",
        password="Sufficiently-Long-Pw-1",
    )
    u.profile.roster_person = mike
    u.profile.save()
    return u


@pytest.fixture
def linked_client(client, linked_user):
    client.force_login(linked_user)
    return client


@pytest.fixture
def projects_per_person(db, user, category, mike, laurel):
    today = dt.date.today()
    p_mike = Project.objects.create(
        title="Mike's task", category=category, created_by=user,
        status=ProjectStatus.IN_PROGRESS,
        projected_completion_date=today + dt.timedelta(days=3),
    )
    RACIAssignment.objects.create(project=p_mike, person=mike, role=RACIRole.RESPONSIBLE)
    p_laurel = Project.objects.create(
        title="Laurel's task", category=category, created_by=user,
        status=ProjectStatus.IN_PROGRESS,
        projected_completion_date=today + dt.timedelta(days=3),
    )
    RACIAssignment.objects.create(project=p_laurel, person=laurel, role=RACIRole.RESPONSIBLE)
    return p_mike, p_laurel


@pytest.mark.django_db
def test_unlinked_user_sees_unlinked_banner_flag(auth_client, projects_per_person):
    response = auth_client.get(reverse("home"))
    assert response.context["unlinked_user_banner"] is True
    # And no filter applied: both projects' "In progress" count is 2.
    assert response.context["stats"]["in_progress"] == 2


@pytest.mark.django_db
def test_linked_user_defaults_to_their_person(linked_client, projects_per_person):
    response = linked_client.get(reverse("home"))
    assert response.context["unlinked_user_banner"] is False
    # Filtered to Mike's project only.
    assert response.context["stats"]["in_progress"] == 1
    titles = [p.title for p in response.context["upcoming"]]
    assert titles == ["Mike's task"]


@pytest.mark.django_db
def test_explicit_all_overrides_default(linked_client, projects_per_person):
    response = linked_client.get(reverse("home") + "?person=all")
    assert response.context["stats"]["in_progress"] == 2


@pytest.mark.django_db
def test_explicit_other_person_filters_to_them(linked_client, projects_per_person, laurel):
    response = linked_client.get(reverse("home") + f"?person={laurel.pk}")
    assert response.context["stats"]["in_progress"] == 1
    titles = [p.title for p in response.context["upcoming"]]
    assert titles == ["Laurel's task"]


@pytest.mark.django_db
def test_activity_feed_scoped_to_filtered_person(
    linked_client, projects_per_person, user, mike,
):
    p_mike, p_laurel = projects_per_person
    ActivityLog.objects.create(
        actor=user, project=p_mike, verb="changed status of",
    )
    ActivityLog.objects.create(
        actor=user, project=p_laurel, verb="changed status of",
    )
    response = linked_client.get(reverse("home"))
    project_titles = [log.project.title for log in response.context["activity"]]
    assert "Mike's task" in project_titles
    assert "Laurel's task" not in project_titles


@pytest.mark.django_db
def test_unlinked_banner_renders_for_unlinked_user(auth_client):
    response = auth_client.get(reverse("home"))
    content = response.content.decode()
    assert "Link your account to a roster person" in content


@pytest.mark.django_db
def test_unlinked_banner_does_not_render_for_linked_user(linked_client):
    response = linked_client.get(reverse("home"))
    content = response.content.decode()
    assert "Link your account to a roster person" not in content


@pytest.mark.django_db
def test_person_dropdown_renders_options(linked_client, projects_per_person, mike, laurel):
    response = linked_client.get(reverse("home"))
    content = response.content.decode()
    # The dropdown options include both active people and an "All people" option.
    assert "All people" in content
    assert ">Mike Smith" in content or "Mike Smith</option>" in content
    assert ">Laurel Baran" in content or "Laurel Baran</option>" in content


@pytest.mark.django_db
def test_recurring_panel_includes_not_started_instances(auth_client, user, category):
    today = dt.date.today()
    template = Project.objects.create(
        title="Monthly review", category=category, created_by=user,
        is_recurring_template=True, is_active=True,
        recurrence_rule="monthly",
        next_due_date=today + dt.timedelta(days=30),
    )
    Project.objects.create(
        title="Monthly review — May 2026", category=category, created_by=user,
        is_recurring_template=False,
        status=ProjectStatus.NOT_STARTED,
        parent_template=template,
        projected_completion_date=today + dt.timedelta(days=30),
    )
    response = auth_client.get(reverse("home"))
    titles = [p.title for p in response.context["recurring_on_deck"]]
    assert "Monthly review — May 2026" in titles


@pytest.mark.django_db
def test_recurring_panel_excludes_one_off_not_started(auth_client, user, category):
    Project.objects.create(
        title="One-off draft", category=category, created_by=user,
        status=ProjectStatus.NOT_STARTED,
        parent_template=None,
    )
    response = auth_client.get(reverse("home"))
    titles = [p.title for p in response.context["recurring_on_deck"]]
    assert "One-off draft" not in titles


@pytest.mark.django_db
def test_recurring_panel_excludes_in_progress_recurring(auth_client, user, category):
    today = dt.date.today()
    template = Project.objects.create(
        title="Monthly review", category=category, created_by=user,
        is_recurring_template=True, is_active=True,
        recurrence_rule="monthly",
        next_due_date=today + dt.timedelta(days=30),
    )
    Project.objects.create(
        title="Started instance", category=category, created_by=user,
        is_recurring_template=False,
        status=ProjectStatus.IN_PROGRESS,
        parent_template=template,
    )
    response = auth_client.get(reverse("home"))
    titles = [p.title for p in response.context["recurring_on_deck"]]
    assert "Started instance" not in titles


@pytest.mark.django_db
def test_recurring_panel_respects_person_filter(linked_client, user, category, mike, laurel):
    today = dt.date.today()
    template = Project.objects.create(
        title="Monthly review", category=category, created_by=user,
        is_recurring_template=True, is_active=True,
        recurrence_rule="monthly",
        next_due_date=today + dt.timedelta(days=30),
    )
    mikes_instance = Project.objects.create(
        title="For Mike", category=category, created_by=user,
        is_recurring_template=False, status=ProjectStatus.NOT_STARTED,
        parent_template=template,
    )
    RACIAssignment.objects.create(
        project=mikes_instance, person=mike, role=RACIRole.RESPONSIBLE,
    )
    laurels_instance = Project.objects.create(
        title="For Laurel", category=category, created_by=user,
        is_recurring_template=False, status=ProjectStatus.NOT_STARTED,
        parent_template=template,
    )
    RACIAssignment.objects.create(
        project=laurels_instance, person=laurel, role=RACIRole.RESPONSIBLE,
    )
    response = linked_client.get(reverse("home"))
    titles = [p.title for p in response.context["recurring_on_deck"]]
    assert titles == ["For Mike"]
