import datetime as dt
from unittest.mock import patch

import pytest
from django.core.management import call_command

from apps.projects.models import Project, RACIAssignment, RACIRole, RecurrenceRule


@pytest.fixture
def template(user, category, person):
    t = Project.objects.create(
        title="Financial review", category=category, created_by=user,
        is_recurring_template=True, is_active=True,
        recurrence_rule=RecurrenceRule.MONTHLY,
        next_due_date=dt.date(2026, 5, 1),
    )
    RACIAssignment.objects.create(project=t, person=person, role=RACIRole.RESPONSIBLE)
    return t


@pytest.mark.django_db
def test_generates_one_instance_when_due(template):
    with patch("apps.projects.management.commands.generate_recurring_instances.dt") as fake_dt:
        fake_dt.date.today.return_value = dt.date(2026, 5, 1)
        fake_dt.date.side_effect = lambda *a, **kw: dt.date(*a, **kw)
        call_command("generate_recurring_instances")

    template.refresh_from_db()
    instance = Project.instances.filter(parent_template=template).first()
    assert instance is not None
    assert instance.title == "Financial review — May 2026"
    assert instance.is_recurring_template is False
    raci = instance.raci_assignments.first()
    assert raci is not None
    assert template.next_due_date == dt.date(2026, 6, 1)


@pytest.mark.django_db
def test_idempotent_in_same_day(template):
    with patch("apps.projects.management.commands.generate_recurring_instances.dt") as fake_dt:
        fake_dt.date.today.return_value = dt.date(2026, 5, 1)
        fake_dt.date.side_effect = lambda *a, **kw: dt.date(*a, **kw)
        call_command("generate_recurring_instances")
        call_command("generate_recurring_instances")

    assert Project.instances.filter(parent_template=template).count() == 1


@pytest.mark.django_db
def test_catches_up_after_missed_cycles(template):
    template.next_due_date = dt.date(2026, 2, 1)
    template.save()
    with patch("apps.projects.management.commands.generate_recurring_instances.dt") as fake_dt:
        fake_dt.date.today.return_value = dt.date(2026, 5, 1)
        fake_dt.date.side_effect = lambda *a, **kw: dt.date(*a, **kw)
        call_command("generate_recurring_instances")
    template.refresh_from_db()
    assert Project.instances.filter(parent_template=template).count() == 4
    assert template.next_due_date == dt.date(2026, 6, 1)


@pytest.mark.django_db
def test_paused_template_skipped(template):
    template.is_active = False
    template.save()
    with patch("apps.projects.management.commands.generate_recurring_instances.dt") as fake_dt:
        fake_dt.date.today.return_value = dt.date(2026, 6, 1)
        fake_dt.date.side_effect = lambda *a, **kw: dt.date(*a, **kw)
        call_command("generate_recurring_instances")
    assert Project.instances.filter(parent_template=template).count() == 0
