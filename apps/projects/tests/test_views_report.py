import datetime as dt
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.projects.models import Project, ProjectCategory, ProjectStatus


def _complete_on(date, project):
    Project.objects.filter(pk=project.pk).update(actual_completion_date=date)
    project.refresh_from_db()
    return project


@pytest.mark.django_db
def test_report_requires_login(client):
    response = client.get(reverse("projects:report"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_report_default_window_is_current_year(auth_client):
    response = auth_client.get(reverse("projects:report"))
    assert response.status_code == 200
    today = dt.date.today()
    assert response.context["from_date"] == dt.date(today.year, 1, 1)
    assert response.context["to_date"] == today


@pytest.mark.django_db
def test_report_honors_explicit_window(auth_client):
    response = auth_client.get(
        reverse("projects:report") + "?from=2026-03-01&to=2026-03-31",
    )
    assert response.context["from_date"] == dt.date(2026, 3, 1)
    assert response.context["to_date"] == dt.date(2026, 3, 31)


@pytest.mark.django_db
def test_report_invalid_dates_fall_back_to_default(auth_client):
    response = auth_client.get(
        reverse("projects:report") + "?from=not-a-date&to=also-bad",
    )
    today = dt.date.today()
    assert response.context["from_date"] == dt.date(today.year, 1, 1)
    assert response.context["to_date"] == today


@pytest.mark.django_db
def test_report_shows_summary_tiles(auth_client, user, category):
    p = Project.objects.create(
        title="X", category=category, created_by=user,
        status=ProjectStatus.COMPLETED, actual_cost=Decimal("250"),
    )
    _complete_on(dt.date(2026, 3, 15), p)
    response = auth_client.get(
        reverse("projects:report") + "?from=2026-01-01&to=2026-12-31",
    )
    content = response.content.decode()
    assert response.context["report"]["summary"]["completed"] == 1
    assert "250" in content


@pytest.mark.django_db
def test_report_renders_category_breakdown_table(auth_client, user):
    landscaping = ProjectCategory.objects.create(name="Landscaping", display_order=1)
    pool = ProjectCategory.objects.create(name="Pool", display_order=2)
    p1 = Project.objects.create(
        title="L", category=landscaping, created_by=user,
        status=ProjectStatus.COMPLETED, actual_cost=Decimal("100"),
    )
    p2 = Project.objects.create(
        title="P", category=pool, created_by=user,
        status=ProjectStatus.COMPLETED, actual_cost=Decimal("200"),
    )
    _complete_on(dt.date(2026, 3, 15), p1)
    _complete_on(dt.date(2026, 3, 15), p2)
    response = auth_client.get(
        reverse("projects:report") + "?from=2026-01-01&to=2026-12-31",
    )
    content = response.content.decode()
    assert "Landscaping" in content
    assert "Pool" in content


@pytest.mark.django_db
def test_report_empty_window_shows_message(auth_client):
    response = auth_client.get(
        reverse("projects:report") + "?from=2030-01-01&to=2030-12-31",
    )
    content = response.content.decode()
    assert "No completed projects" in content


@pytest.mark.django_db
def test_sidebar_includes_reports_link(auth_client):
    response = auth_client.get(reverse("home"))
    content = response.content.decode()
    assert ">Reports<" in content
    assert reverse("projects:report") in content
