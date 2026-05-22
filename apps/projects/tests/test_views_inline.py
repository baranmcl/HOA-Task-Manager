import pytest
from django.urls import reverse

from apps.projects.models import ActivityLog, ProjectStatus


@pytest.mark.django_db
def test_status_edit_form_renders(auth_client, project):
    response = auth_client.get(reverse("projects:inline_status_edit", args=[project.pk]))
    assert response.status_code == 200
    assert b"<select" in response.content


@pytest.mark.django_db
def test_status_save_updates_and_logs(auth_client, project):
    response = auth_client.post(
        reverse("projects:inline_status_save", args=[project.pk]),
        {"status": "in_progress"},
    )
    assert response.status_code == 200
    project.refresh_from_db()
    assert project.status == "in_progress"
    assert ActivityLog.objects.filter(project=project, verb="changed status").exists()


@pytest.mark.django_db
def test_status_save_delayed_requires_reason(auth_client, project):
    response = auth_client.post(
        reverse("projects:inline_status_save", args=[project.pk]),
        {"status": "delayed", "delay_reason": ""},
    )
    assert response.status_code == 400
    project.refresh_from_db()
    assert project.status != ProjectStatus.DELAYED


@pytest.mark.django_db
def test_priority_save(auth_client, project):
    response = auth_client.post(
        reverse("projects:inline_priority_save", args=[project.pk]),
        {"priority": "high"},
    )
    assert response.status_code == 200
    project.refresh_from_db()
    assert project.priority == "high"


@pytest.mark.django_db
def test_dates_save(auth_client, project):
    response = auth_client.post(
        reverse("projects:inline_dates_save", args=[project.pk]),
        {"projected_completion_date": "2026-12-01"},
    )
    assert response.status_code == 200
    project.refresh_from_db()
    assert str(project.projected_completion_date) == "2026-12-01"


@pytest.mark.django_db
def test_budget_save(auth_client, project):
    response = auth_client.post(
        reverse("projects:inline_budget_save", args=[project.pk]),
        {"budget_amount": "5000.00", "actual_cost": "2500.00"},
    )
    assert response.status_code == 200
    project.refresh_from_db()
    assert str(project.budget_amount) == "5000.00"


@pytest.mark.django_db
def test_vendor_save(auth_client, project):
    response = auth_client.post(
        reverse("projects:inline_vendor_save", args=[project.pk]),
        {"vendor_name": "ABC Inc", "vendor_bid_amount": "10000.00"},
    )
    assert response.status_code == 200
    project.refresh_from_db()
    assert project.vendor_name == "ABC Inc"
