"""Tests for the Pass A navigation polish: clickable dashboard tiles
(with new filter shortcuts on the project list), the back-navigation
context processor, and the 'Clear filters' affordances.
"""
import datetime as dt

import pytest
from django.urls import reverse

from apps.projects.context_processors import back_navigation
from apps.projects.models import Project, ProjectStatus

# ---- Dashboard tile click-through ---------------------------------------

@pytest.mark.django_db
def test_dashboard_overdue_tile_links_to_filtered_list(auth_client):
    response = auth_client.get(reverse("home"))
    content = response.content.decode()
    expected = reverse("projects:list") + "?overdue=1"
    assert expected in content


@pytest.mark.django_db
def test_dashboard_upcoming_tile_links_to_filtered_list(auth_client):
    response = auth_client.get(reverse("home"))
    content = response.content.decode()
    expected = reverse("projects:list") + "?upcoming=1"
    assert expected in content


@pytest.mark.django_db
def test_dashboard_in_progress_tile_links_to_filtered_list(auth_client):
    response = auth_client.get(reverse("home"))
    content = response.content.decode()
    expected = reverse("projects:list") + "?status=in_progress"
    assert expected in content


@pytest.mark.django_db
def test_dashboard_completed_this_month_tile_links_to_filtered_list(auth_client):
    response = auth_client.get(reverse("home"))
    content = response.content.decode()
    expected = reverse("projects:list") + "?completed_this_month=1"
    assert expected in content


@pytest.mark.django_db
def test_dashboard_tiles_preserve_person_filter(auth_client):
    """If the dashboard is filtered to a person, clicking a tile should
    carry the person filter through to the list view."""
    response = auth_client.get(reverse("home") + "?person=42")
    content = response.content.decode()
    assert reverse("projects:list") + "?overdue=1&person=42" in content
    assert reverse("projects:list") + "?upcoming=1&person=42" in content


# ---- New list-view filter shortcuts -------------------------------------

@pytest.mark.django_db
def test_list_view_overdue_filter(auth_client, user, category):
    today = dt.date.today()
    overdue = Project.objects.create(
        title="Late", category=category, created_by=user,
        status=ProjectStatus.IN_PROGRESS,
        projected_completion_date=today - dt.timedelta(days=3),
    )
    future = Project.objects.create(
        title="Future", category=category, created_by=user,
        status=ProjectStatus.IN_PROGRESS,
        projected_completion_date=today + dt.timedelta(days=3),
    )
    response = auth_client.get(reverse("projects:list") + "?overdue=1")
    titles = [p.title for p in response.context["projects"]]
    assert overdue.title in titles
    assert future.title not in titles


@pytest.mark.django_db
def test_list_view_overdue_excludes_completed(auth_client, user, category):
    today = dt.date.today()
    Project.objects.create(
        title="Done late", category=category, created_by=user,
        status=ProjectStatus.COMPLETED,
        projected_completion_date=today - dt.timedelta(days=3),
    )
    response = auth_client.get(reverse("projects:list") + "?overdue=1")
    titles = [p.title for p in response.context["projects"]]
    assert "Done late" not in titles


@pytest.mark.django_db
def test_list_view_upcoming_filter(auth_client, user, category):
    today = dt.date.today()
    in_window = Project.objects.create(
        title="Soon", category=category, created_by=user,
        status=ProjectStatus.IN_PROGRESS,
        projected_completion_date=today + dt.timedelta(days=7),
    )
    too_far = Project.objects.create(
        title="Far", category=category, created_by=user,
        status=ProjectStatus.IN_PROGRESS,
        projected_completion_date=today + dt.timedelta(days=30),
    )
    response = auth_client.get(reverse("projects:list") + "?upcoming=1")
    titles = [p.title for p in response.context["projects"]]
    assert in_window.title in titles
    assert too_far.title not in titles


@pytest.mark.django_db
def test_list_view_completed_this_month_filter(auth_client, user, category):
    today = dt.date.today()
    first_of_month = today.replace(day=1)
    this_month = Project.objects.create(
        title="Done this month", category=category, created_by=user,
        status=ProjectStatus.COMPLETED,
    )
    Project.objects.filter(pk=this_month.pk).update(
        actual_completion_date=first_of_month + dt.timedelta(days=2),
    )
    last_month_date = (first_of_month - dt.timedelta(days=10)).replace(day=15)
    last_month = Project.objects.create(
        title="Done last month", category=category, created_by=user,
        status=ProjectStatus.COMPLETED,
    )
    Project.objects.filter(pk=last_month.pk).update(
        actual_completion_date=last_month_date,
    )
    response = auth_client.get(reverse("projects:list") + "?completed_this_month=1")
    titles = [p.title for p in response.context["projects"]]
    assert this_month.title in titles
    assert last_month.title not in titles


@pytest.mark.django_db
def test_list_view_shortcut_label_appears(auth_client):
    response = auth_client.get(reverse("projects:list") + "?overdue=1")
    assert "Overdue projects" in response.content.decode()

    response = auth_client.get(reverse("projects:list") + "?upcoming=1")
    assert "Upcoming projects" in response.content.decode()

    response = auth_client.get(reverse("projects:list") + "?completed_this_month=1")
    assert "Done this month" in response.content.decode()


# ---- Clear filters -------------------------------------------------------

@pytest.mark.django_db
def test_list_clear_filters_link_hidden_when_no_filters_active(auth_client):
    response = auth_client.get(reverse("projects:list"))
    assert response.context["any_filter_active"] is False
    assert "Clear filters" not in response.content.decode()


@pytest.mark.django_db
def test_list_clear_filters_link_shown_when_filter_active(auth_client):
    response = auth_client.get(reverse("projects:list") + "?status=in_progress")
    assert response.context["any_filter_active"] is True
    assert "Clear filters" in response.content.decode()


@pytest.mark.django_db
def test_board_clear_filters_link_shown_when_show_completed_active(auth_client):
    response = auth_client.get(reverse("projects:board") + "?show_completed=1")
    assert "Clear filters" in response.content.decode()


@pytest.mark.django_db
def test_board_clear_filters_link_hidden_by_default(auth_client):
    response = auth_client.get(reverse("projects:board"))
    assert "Clear filters" not in response.content.decode()


# ---- Back navigation context processor ----------------------------------

class FakeRequest:
    def __init__(self, referer="", path="/projects/1/", host="testserver"):
        self.META = {"HTTP_REFERER": referer} if referer else {}
        self.path = path
        self._host = host

    def get_host(self):
        return self._host


def test_back_nav_empty_when_no_referer():
    ctx = back_navigation(FakeRequest(referer=""))
    assert ctx["back_url"] == ""
    assert ctx["back_label"] == ""


def test_back_nav_empty_when_referer_is_cross_origin():
    ctx = back_navigation(FakeRequest(referer="https://evil.example/"))
    assert ctx["back_url"] == ""
    assert ctx["back_label"] == ""


def test_back_nav_empty_when_referer_matches_current_path():
    ctx = back_navigation(FakeRequest(
        referer="https://testserver/projects/1/",
        path="/projects/1/",
    ))
    assert ctx["back_url"] == ""


def test_back_nav_resolves_dashboard():
    ctx = back_navigation(FakeRequest(
        referer="https://testserver/",
        path="/projects/1/",
    ))
    assert ctx["back_url"] == "https://testserver/"
    assert ctx["back_label"] == "Dashboard"


def test_back_nav_resolves_board():
    ctx = back_navigation(FakeRequest(
        referer="https://testserver/projects/board/",
        path="/projects/1/",
    ))
    assert ctx["back_label"] == "Board"


def test_back_nav_resolves_calendar():
    ctx = back_navigation(FakeRequest(
        referer="https://testserver/projects/calendar/",
        path="/projects/1/",
    ))
    assert ctx["back_label"] == "Calendar"


def test_back_nav_resolves_projects_list():
    ctx = back_navigation(FakeRequest(
        referer="https://testserver/projects/",
        path="/projects/1/",
    ))
    assert ctx["back_label"] == "Projects"


def test_back_nav_resolves_calendar_at():
    """The dated calendar URL (projects:calendar_at) should map to
    'Calendar' too — both names live in the allowlist."""
    ctx = back_navigation(FakeRequest(
        referer="https://testserver/projects/calendar/2026/6/",
        path="/projects/1/",
    ))
    assert ctx["back_label"] == "Calendar"


def test_back_nav_empty_for_unknown_route():
    """A referer that resolves to a route NOT in the allowlist (e.g.,
    an admin page) returns empty, so we don't surface a confusing link."""
    ctx = back_navigation(FakeRequest(
        referer="https://testserver/admin/",
        path="/projects/1/",
    ))
    assert ctx["back_url"] == ""


# ---- Back link rendered in templates -----------------------------------

@pytest.mark.django_db
def test_detail_page_shows_back_link_when_referer_set(auth_client, project):
    response = auth_client.get(
        reverse("projects:detail", kwargs={"pk": project.pk}),
        HTTP_REFERER="http://testserver/",
    )
    content = response.content.decode()
    assert "Back to Dashboard" in content


@pytest.mark.django_db
def test_detail_page_hides_back_link_when_no_referer(auth_client, project):
    response = auth_client.get(
        reverse("projects:detail", kwargs={"pk": project.pk}),
    )
    content = response.content.decode()
    assert "Back to" not in content
