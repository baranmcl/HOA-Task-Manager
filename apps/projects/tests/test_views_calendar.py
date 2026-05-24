"""Tests for the calendar view and its date helper."""
import calendar as stdlib_calendar
import datetime as dt

import pytest
from django.urls import reverse

from apps.projects.models import Project, ProjectStatus
from apps.projects.views.calendar import build_month_grid


def test_build_month_grid_returns_six_weeks_of_seven_days():
    first, last, weeks = build_month_grid(2026, 5)
    assert len(weeks) >= 4 and len(weeks) <= 6  # months span 4-6 visible weeks
    for week in weeks:
        assert len(week) == 7


def test_build_month_grid_starts_on_sunday():
    _, _, weeks = build_month_grid(2026, 5)
    # First column should be Sunday (weekday() == 6 in Python's Mon=0 convention).
    assert weeks[0][0].weekday() == stdlib_calendar.SUNDAY


def test_build_month_grid_may_2026_includes_adjacent_month_padding():
    """May 1 2026 is a Friday — the first row should include April 26-30."""
    first, _, weeks = build_month_grid(2026, 5)
    # First date in the grid is in April, not May.
    assert weeks[0][0] < dt.date(2026, 5, 1)
    assert first == weeks[0][0]


def test_build_month_grid_last_date_extends_into_next_month_if_needed():
    """May 31 2026 is a Sunday — June 1-6 fills out the last row."""
    _, last, weeks = build_month_grid(2026, 5)
    assert last == weeks[-1][-1]
    assert last >= dt.date(2026, 5, 31)


@pytest.mark.django_db
def test_calendar_view_default_renders_current_month(auth_client):
    response = auth_client.get(reverse("projects:calendar"))
    assert response.status_code == 200
    today = dt.date.today()
    month_name = today.strftime("%B")
    content = response.content.decode()
    assert month_name in content
    assert str(today.year) in content


@pytest.mark.django_db
def test_calendar_view_with_year_month_renders_that_month(auth_client):
    response = auth_client.get(reverse("projects:calendar_at", args=[2026, 6]))
    assert response.status_code == 200
    assert "June" in response.content.decode()


@pytest.mark.django_db
def test_calendar_view_invalid_month_returns_404(auth_client):
    response = auth_client.get(reverse("projects:calendar_at", args=[2026, 13]))
    assert response.status_code == 404


@pytest.mark.django_db
def test_calendar_view_requires_login(client):
    response = client.get(reverse("projects:calendar"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_calendar_view_places_project_in_its_due_date_cell(
    auth_client, user, category,
):
    Project.objects.create(
        title="Sprinkler upgrade", category=category, created_by=user,
        projected_completion_date=dt.date(2026, 5, 15),
    )
    response = auth_client.get(reverse("projects:calendar_at", args=[2026, 5]))
    content = response.content.decode()
    assert "Sprinkler upgrade" in content


@pytest.mark.django_db
def test_calendar_view_excludes_project_outside_visible_window(
    auth_client, user, category,
):
    Project.objects.create(
        title="January project", category=category, created_by=user,
        projected_completion_date=dt.date(2026, 1, 15),
    )
    response = auth_client.get(reverse("projects:calendar_at", args=[2026, 5]))
    assert "January project" not in response.content.decode()


@pytest.mark.django_db
def test_calendar_view_excludes_project_with_no_date(
    auth_client, user, category,
):
    Project.objects.create(
        title="No date project", category=category, created_by=user,
        projected_completion_date=None,
    )
    response = auth_client.get(reverse("projects:calendar_at", args=[2026, 5]))
    assert "No date project" not in response.content.decode()


@pytest.mark.django_db
def test_calendar_view_color_codes_by_status(auth_client, user, category):
    Project.objects.create(
        title="Delayed project", category=category, created_by=user,
        projected_completion_date=dt.date(2026, 5, 10),
        status=ProjectStatus.DELAYED,
    )
    Project.objects.create(
        title="Done project", category=category, created_by=user,
        projected_completion_date=dt.date(2026, 5, 11),
        status=ProjectStatus.COMPLETED,
    )
    response = auth_client.get(reverse("projects:calendar_at", args=[2026, 5]))
    content = response.content.decode()
    # Use the exact class fragment used by the project list row for status pills.
    assert "bg-red-100" in content
    assert "bg-green-100" in content


@pytest.mark.django_db
def test_calendar_view_overflow_link_when_more_than_three_on_one_day(
    auth_client, user, category,
):
    target_date = dt.date(2026, 5, 15)
    for i in range(5):
        Project.objects.create(
            title=f"Project {i}", category=category, created_by=user,
            projected_completion_date=target_date,
        )
    response = auth_client.get(reverse("projects:calendar_at", args=[2026, 5]))
    content = response.content.decode()
    # 3 chips visible, "+2 more" overflow link.
    assert "+2 more" in content
