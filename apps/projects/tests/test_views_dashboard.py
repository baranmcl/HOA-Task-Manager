import datetime as dt

import pytest
from django.urls import reverse

from apps.projects.models import Project, ProjectStatus


@pytest.mark.django_db
def test_dashboard_renders(auth_client):
    response = auth_client.get(reverse("home"))
    assert response.status_code == 200
    assert b"Dashboard" in response.content


@pytest.mark.django_db
def test_dashboard_shows_overdue(auth_client, user, category):
    today = dt.date.today()
    Project.objects.create(
        title="OldOverdue", category=category, created_by=user,
        status=ProjectStatus.IN_PROGRESS,
        projected_completion_date=today - dt.timedelta(days=5),
    )
    response = auth_client.get(reverse("home"))
    assert b"OldOverdue" in response.content


@pytest.mark.django_db
def test_dashboard_excludes_templates(auth_client, user, category):
    Project.objects.create(
        title="TemplateOnly", category=category, created_by=user,
        is_recurring_template=True,
    )
    response = auth_client.get(reverse("home"))
    assert b"TemplateOnly" not in response.content
