import datetime as dt
from decimal import Decimal

import pytest

from apps.projects.models import Project, ProjectPriority, ProjectStatus


@pytest.mark.django_db
def test_create_project_minimal(user, category):
    p = Project.objects.create(
        title="Sprinkler upgrade",
        category=category,
        created_by=user,
    )
    assert p.status == ProjectStatus.NOT_STARTED
    assert p.priority == ProjectPriority.MEDIUM
    assert p.is_active is True
    assert p.is_recurring_template is False
    assert p.actual_completion_date is None


@pytest.mark.django_db
def test_completing_project_sets_actual_date(user, category):
    p = Project.objects.create(title="X", category=category, created_by=user)
    p.status = ProjectStatus.COMPLETED
    p.save()
    assert p.actual_completion_date == dt.date.today()


@pytest.mark.django_db
def test_completed_to_not_started_clears_actual_date(user, category):
    p = Project.objects.create(title="X", category=category, created_by=user)
    p.status = ProjectStatus.COMPLETED
    p.save()
    p.status = ProjectStatus.NOT_STARTED
    p.save()
    assert p.actual_completion_date is None


@pytest.mark.django_db
def test_str_uses_title(user, category):
    p = Project.objects.create(title="Concrete repair", category=category, created_by=user)
    assert str(p) == "Concrete repair"


@pytest.mark.django_db
def test_decimal_money_fields(user, category):
    p = Project.objects.create(
        title="X", category=category, created_by=user,
        budget_amount=Decimal("12345.67"),
        actual_cost=Decimal("100.00"),
    )
    p.refresh_from_db()
    assert p.budget_amount == Decimal("12345.67")


@pytest.mark.django_db
def test_recurring_template_flag(user, category):
    template = Project.objects.create(
        title="Monthly review", category=category, created_by=user,
        is_recurring_template=True,
        recurrence_rule="monthly",
        next_due_date=dt.date(2026, 6, 1),
    )
    assert template.is_recurring_template is True
    assert template.recurrence_rule == "monthly"


@pytest.mark.django_db
def test_overdue_property_for_in_progress(user, category):
    today = dt.date.today()
    p = Project.objects.create(
        title="X", category=category, created_by=user,
        status=ProjectStatus.IN_PROGRESS,
        projected_completion_date=today - dt.timedelta(days=1),
    )
    assert p.is_overdue is True


@pytest.mark.django_db
def test_completed_is_never_overdue(user, category):
    today = dt.date.today()
    p = Project.objects.create(
        title="X", category=category, created_by=user,
        status=ProjectStatus.COMPLETED,
        projected_completion_date=today - dt.timedelta(days=10),
    )
    assert p.is_overdue is False


@pytest.mark.django_db
def test_active_manager_excludes_templates(user, category):
    Project.objects.create(title="A", category=category, created_by=user)
    Project.objects.create(
        title="T", category=category, created_by=user,
        is_recurring_template=True,
    )
    assert Project.instances.count() == 1
    assert Project.objects.count() == 2
