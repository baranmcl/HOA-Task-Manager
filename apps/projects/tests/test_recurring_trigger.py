import datetime as dt

import pytest
from django.db import IntegrityError
from django.urls import reverse

from apps.projects import middleware
from apps.projects.models import GenerationLog, Project, RecurrenceRule


@pytest.mark.django_db
def test_generation_log_run_date_unique():
    GenerationLog.objects.create(run_date=dt.date(2026, 5, 1))
    with pytest.raises(IntegrityError):
        GenerationLog.objects.create(run_date=dt.date(2026, 5, 1))


@pytest.mark.django_db
def test_first_request_of_day_runs_generator(auth_client, user, category):
    Project.objects.create(
        title="Monthly review", category=category, created_by=user,
        is_recurring_template=True, is_active=True,
        recurrence_rule=RecurrenceRule.MONTHLY,
        next_due_date=dt.date.today(),
    )
    assert Project.instances.count() == 0
    auth_client.get(reverse("projects:list"))
    assert GenerationLog.objects.filter(run_date=dt.date.today()).exists()
    assert Project.instances.filter(parent_template__isnull=False).count() >= 1


@pytest.mark.django_db
def test_second_request_same_day_does_not_rerun(auth_client, user, category):
    Project.objects.create(
        title="Monthly review", category=category, created_by=user,
        is_recurring_template=True, is_active=True,
        recurrence_rule=RecurrenceRule.MONTHLY,
        next_due_date=dt.date.today(),
    )
    auth_client.get(reverse("projects:list"))
    count_after_first = Project.instances.count()
    assert count_after_first >= 1
    auth_client.get(reverse("projects:list"))
    assert Project.instances.count() == count_after_first


@pytest.mark.django_db
def test_generator_failure_does_not_break_request(auth_client, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("generator exploded")
    monkeypatch.setattr(middleware, "call_command", boom)
    response = auth_client.get(reverse("projects:list"))
    assert response.status_code == 200
