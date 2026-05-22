import datetime as dt

import pytest
from django.urls import reverse

from apps.projects.models import Project, RecurrenceRule


@pytest.mark.django_db
def test_list_renders_only_templates(auth_client, user, category):
    Project.objects.create(title="Plain", category=category, created_by=user)
    Project.objects.create(
        title="Template", category=category, created_by=user,
        is_recurring_template=True, recurrence_rule=RecurrenceRule.MONTHLY,
        next_due_date=dt.date(2026, 6, 1),
    )
    response = auth_client.get(reverse("projects:recurring_list"))
    assert b"Template" in response.content
    assert b"Plain" not in response.content


@pytest.mark.django_db
def test_create_template(auth_client, category):
    response = auth_client.post(reverse("projects:recurring_create"), {
        "title": "Monthly review",
        "description": "",
        "category": category.pk,
        "priority": "medium",
        "recurrence_rule": "monthly",
        "next_due_date": "2026-06-01",
        "is_active": "on",
    })
    assert response.status_code == 302
    assert Project.templates.filter(title="Monthly review").exists()


@pytest.mark.django_db
def test_pause_template(auth_client, user, category):
    t = Project.objects.create(
        title="X", category=category, created_by=user,
        is_recurring_template=True, recurrence_rule=RecurrenceRule.MONTHLY,
        next_due_date=dt.date(2026, 6, 1), is_active=True,
    )
    response = auth_client.post(reverse("projects:recurring_toggle", args=[t.pk]))
    assert response.status_code == 302
    t.refresh_from_db()
    assert t.is_active is False
