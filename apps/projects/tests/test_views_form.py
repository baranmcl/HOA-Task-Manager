from decimal import Decimal

import pytest
from django.urls import reverse

from apps.projects.models import Project


@pytest.mark.django_db
def test_create_get_renders(auth_client, category):
    response = auth_client.get(reverse("projects:create"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_create_post_creates_project(auth_client, category):
    response = auth_client.post(reverse("projects:create"), {
        "title": "New Project",
        "category": category.pk,
        "status": "not_started",
        "priority": "medium",
        "description": "",
        "tags_text": "",
    })
    assert response.status_code == 302
    assert Project.objects.filter(title="New Project").exists()


@pytest.mark.django_db
def test_edit_post_updates(auth_client, project):
    response = auth_client.post(reverse("projects:edit", args=[project.pk]), {
        "title": "Renamed",
        "category": project.category_id,
        "status": "not_started",
        "priority": "high",
        "description": "",
        "tags_text": "",
    })
    assert response.status_code == 302
    project.refresh_from_db()
    assert project.title == "Renamed"
    assert project.priority == "high"


@pytest.mark.django_db
def test_create_form_financial_section_collapsed(auth_client, category):
    response = auth_client.get(reverse("projects:create"))
    content = response.content.decode()
    assert "<details" in content
    assert "<details open" not in content


@pytest.mark.django_db
def test_edit_form_financial_section_open_when_data_present(auth_client, project):
    project.budget_amount = Decimal("1500.00")
    project.save()
    response = auth_client.get(reverse("projects:edit", args=[project.pk]))
    assert "<details open" in response.content.decode()


@pytest.mark.django_db
def test_edit_form_financial_section_collapsed_when_no_data(auth_client, project):
    response = auth_client.get(reverse("projects:edit", args=[project.pk]))
    assert "<details open" not in response.content.decode()


@pytest.mark.django_db
def test_create_form_has_delay_reason_js_hooks(auth_client, category):
    """The status select and delay-reason container expose the ids the
    toggle script targets; a regression that removes a hook is caught here."""
    response = auth_client.get(reverse("projects:create"))
    content = response.content.decode()
    assert 'id="id_status"' in content
    assert 'id="delay-reason-field"' in content


@pytest.mark.django_db
def test_create_form_loads_the_toggle_script(auth_client, category):
    response = auth_client.get(reverse("projects:create"))
    assert "js/delay-reason-toggle.js" in response.content.decode()
