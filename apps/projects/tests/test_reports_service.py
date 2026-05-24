import datetime as dt
from decimal import Decimal

import pytest

from apps.projects.models import Project, ProjectCategory, ProjectStatus
from apps.projects.services.reports import compute_completion_report


def _complete_on(date, project):
    Project.objects.filter(pk=project.pk).update(actual_completion_date=date)
    project.refresh_from_db()
    return project


@pytest.mark.django_db
def test_empty_window_returns_zeros(category):
    result = compute_completion_report(dt.date(2026, 1, 1), dt.date(2026, 12, 31))
    assert result["summary"]["completed"] == 0
    assert result["summary"]["total_spent"] == Decimal("0")
    assert result["summary"]["over_budget"] == 0
    assert result["summary"]["avg_days_to_complete"] is None
    assert result["by_category"] == []


@pytest.mark.django_db
def test_completed_in_window_counted(user, category):
    p = Project.objects.create(
        title="Done", category=category, created_by=user,
        status=ProjectStatus.COMPLETED, actual_cost=Decimal("100"),
    )
    _complete_on(dt.date(2026, 3, 15), p)
    result = compute_completion_report(dt.date(2026, 1, 1), dt.date(2026, 12, 31))
    assert result["summary"]["completed"] == 1
    assert result["summary"]["total_spent"] == Decimal("100")


@pytest.mark.django_db
def test_completed_outside_window_excluded(user, category):
    p = Project.objects.create(
        title="Last year", category=category, created_by=user,
        status=ProjectStatus.COMPLETED, actual_cost=Decimal("100"),
    )
    _complete_on(dt.date(2025, 6, 15), p)
    result = compute_completion_report(dt.date(2026, 1, 1), dt.date(2026, 12, 31))
    assert result["summary"]["completed"] == 0


@pytest.mark.django_db
def test_in_progress_excluded_even_inside_window(user, category):
    Project.objects.create(
        title="WIP", category=category, created_by=user,
        status=ProjectStatus.IN_PROGRESS,
    )
    result = compute_completion_report(dt.date(2026, 1, 1), dt.date(2026, 12, 31))
    assert result["summary"]["completed"] == 0


@pytest.mark.django_db
def test_recurring_template_excluded(user, category):
    Project.objects.create(
        title="Template", category=category, created_by=user,
        status=ProjectStatus.COMPLETED, is_recurring_template=True,
    )
    result = compute_completion_report(dt.date(2026, 1, 1), dt.date(2026, 12, 31))
    assert result["summary"]["completed"] == 0


@pytest.mark.django_db
def test_total_spent_treats_null_actual_cost_as_zero(user, category):
    p1 = Project.objects.create(
        title="A", category=category, created_by=user,
        status=ProjectStatus.COMPLETED, actual_cost=Decimal("250"),
    )
    p2 = Project.objects.create(
        title="B", category=category, created_by=user,
        status=ProjectStatus.COMPLETED, actual_cost=None,
    )
    _complete_on(dt.date(2026, 3, 15), p1)
    _complete_on(dt.date(2026, 4, 1), p2)
    result = compute_completion_report(dt.date(2026, 1, 1), dt.date(2026, 12, 31))
    assert result["summary"]["completed"] == 2
    assert result["summary"]["total_spent"] == Decimal("250")


@pytest.mark.django_db
def test_over_budget_requires_both_amounts_set(user, category):
    a = Project.objects.create(
        title="Over", category=category, created_by=user,
        status=ProjectStatus.COMPLETED,
        budget_amount=Decimal("100"), actual_cost=Decimal("150"),
    )
    b = Project.objects.create(
        title="Under", category=category, created_by=user,
        status=ProjectStatus.COMPLETED,
        budget_amount=Decimal("100"), actual_cost=Decimal("80"),
    )
    c = Project.objects.create(
        title="No budget", category=category, created_by=user,
        status=ProjectStatus.COMPLETED,
        budget_amount=None, actual_cost=Decimal("999"),
    )
    for p in (a, b, c):
        _complete_on(dt.date(2026, 3, 15), p)
    result = compute_completion_report(dt.date(2026, 1, 1), dt.date(2026, 12, 31))
    assert result["summary"]["over_budget"] == 1


@pytest.mark.django_db
def test_avg_days_to_complete_math(user, category):
    p1 = Project.objects.create(
        title="Fast", category=category, created_by=user,
        status=ProjectStatus.COMPLETED,
    )
    p2 = Project.objects.create(
        title="Slow", category=category, created_by=user,
        status=ProjectStatus.COMPLETED,
    )
    created_at_fixed = dt.datetime(2026, 3, 1, 12, 0, tzinfo=dt.UTC)
    Project.objects.filter(pk__in=[p1.pk, p2.pk]).update(created_at=created_at_fixed)
    _complete_on(dt.date(2026, 3, 5), p1)
    _complete_on(dt.date(2026, 3, 11), p2)
    result = compute_completion_report(dt.date(2026, 1, 1), dt.date(2026, 12, 31))
    assert result["summary"]["avg_days_to_complete"] == 7


@pytest.mark.django_db
def test_by_category_breakdown(user):
    landscaping = ProjectCategory.objects.create(name="Landscaping", display_order=1)
    pool = ProjectCategory.objects.create(name="Pool", display_order=2)
    ProjectCategory.objects.create(name="Empty", display_order=3)

    p1 = Project.objects.create(
        title="L1", category=landscaping, created_by=user,
        status=ProjectStatus.COMPLETED, actual_cost=Decimal("100"),
    )
    p2 = Project.objects.create(
        title="L2", category=landscaping, created_by=user,
        status=ProjectStatus.COMPLETED, actual_cost=Decimal("300"),
    )
    p3 = Project.objects.create(
        title="P1", category=pool, created_by=user,
        status=ProjectStatus.COMPLETED, actual_cost=Decimal("500"),
    )
    for p in (p1, p2, p3):
        _complete_on(dt.date(2026, 3, 15), p)

    result = compute_completion_report(dt.date(2026, 1, 1), dt.date(2026, 12, 31))
    rows = result["by_category"]
    assert [r["name"] for r in rows] == ["Landscaping", "Pool"]
    assert rows[0]["count"] == 2
    assert rows[0]["total_spent"] == Decimal("400")
    assert rows[0]["avg_cost"] == Decimal("200")
    assert rows[1]["count"] == 1
    assert rows[1]["total_spent"] == Decimal("500")
    assert "Empty" not in [r["name"] for r in rows]


@pytest.mark.django_db
def test_window_boundary_inclusive(user, category):
    p1 = Project.objects.create(
        title="On from", category=category, created_by=user,
        status=ProjectStatus.COMPLETED,
    )
    p2 = Project.objects.create(
        title="On to", category=category, created_by=user,
        status=ProjectStatus.COMPLETED,
    )
    _complete_on(dt.date(2026, 1, 1), p1)
    _complete_on(dt.date(2026, 12, 31), p2)
    result = compute_completion_report(dt.date(2026, 1, 1), dt.date(2026, 12, 31))
    assert result["summary"]["completed"] == 2
