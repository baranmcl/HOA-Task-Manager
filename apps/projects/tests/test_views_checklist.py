"""Tests for the checklist UI on a project: add/toggle/delete + the
"all items complete — mark project Completed?" prompt flow.
"""
import datetime as dt

import pytest
from django.urls import reverse

from apps.projects.models import ChecklistItem, Project, ProjectStatus


@pytest.fixture
def project_with_items(db, user, category):
    project = Project.objects.create(
        title="Bike room reno", category=category, created_by=user,
    )
    return project


# ---- Model tests --------------------------------------------------------

@pytest.mark.django_db
def test_create_checklist_item(project_with_items):
    item = ChecklistItem.objects.create(
        project=project_with_items, text="Survey members", order=0,
    )
    assert str(item) == "[ ] Survey members"
    assert not item.completed
    assert item.completed_at is None
    assert item.completed_by is None


@pytest.mark.django_db
def test_checklist_item_str_when_completed(project_with_items):
    item = ChecklistItem.objects.create(
        project=project_with_items, text="Done thing", completed=True, order=0,
    )
    assert str(item) == "[x] Done thing"


@pytest.mark.django_db
def test_is_overdue_when_past_due_and_incomplete(project_with_items):
    yesterday = dt.date.today() - dt.timedelta(days=1)
    item = ChecklistItem.objects.create(
        project=project_with_items, text="Late", due_date=yesterday, order=0,
    )
    assert item.is_overdue


@pytest.mark.django_db
def test_is_overdue_false_when_completed(project_with_items):
    yesterday = dt.date.today() - dt.timedelta(days=1)
    item = ChecklistItem.objects.create(
        project=project_with_items, text="Done late",
        due_date=yesterday, completed=True, order=0,
    )
    assert not item.is_overdue


@pytest.mark.django_db
def test_is_overdue_false_when_no_due_date(project_with_items):
    item = ChecklistItem.objects.create(
        project=project_with_items, text="No date", order=0,
    )
    assert not item.is_overdue


@pytest.mark.django_db
def test_checklist_default_ordering(project_with_items):
    ChecklistItem.objects.create(project=project_with_items, text="C", order=2)
    ChecklistItem.objects.create(project=project_with_items, text="A", order=0)
    ChecklistItem.objects.create(project=project_with_items, text="B", order=1)
    titles = [i.text for i in project_with_items.checklist_items.all()]
    assert titles == ["A", "B", "C"]


# ---- View tests ---------------------------------------------------------

@pytest.mark.django_db
def test_checklist_add_creates_item(auth_client, project_with_items):
    response = auth_client.post(
        reverse("projects:checklist_add", kwargs={"pk": project_with_items.pk}),
        {"text": "Survey members"},
    )
    assert response.status_code == 200
    assert project_with_items.checklist_items.count() == 1
    item = project_with_items.checklist_items.first()
    assert item.text == "Survey members"
    assert item.order > 0  # auto-appended after the last existing


@pytest.mark.django_db
def test_checklist_add_with_due_date(auth_client, project_with_items):
    auth_client.post(
        reverse("projects:checklist_add", kwargs={"pk": project_with_items.pk}),
        {"text": "Get quotes", "due_date": "2026-07-15"},
    )
    item = project_with_items.checklist_items.first()
    assert item.due_date == dt.date(2026, 7, 15)


@pytest.mark.django_db
def test_checklist_add_rejects_empty_text(auth_client, project_with_items):
    response = auth_client.post(
        reverse("projects:checklist_add", kwargs={"pk": project_with_items.pk}),
        {"text": "   "},
    )
    assert response.status_code == 400
    assert project_with_items.checklist_items.count() == 0


@pytest.mark.django_db
def test_checklist_add_rejects_invalid_date(auth_client, project_with_items):
    response = auth_client.post(
        reverse("projects:checklist_add", kwargs={"pk": project_with_items.pk}),
        {"text": "Do thing", "due_date": "not-a-date"},
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_checklist_add_appends_to_end(auth_client, project_with_items):
    ChecklistItem.objects.create(project=project_with_items, text="First", order=0)
    ChecklistItem.objects.create(project=project_with_items, text="Second", order=1)
    auth_client.post(
        reverse("projects:checklist_add", kwargs={"pk": project_with_items.pk}),
        {"text": "Third"},
    )
    last = project_with_items.checklist_items.last()
    assert last.text == "Third"
    assert last.order == 2


@pytest.mark.django_db
def test_checklist_toggle_marks_complete(auth_client, project_with_items, user):
    item = ChecklistItem.objects.create(
        project=project_with_items, text="Do thing", order=0,
    )
    auth_client.post(
        reverse("projects:checklist_toggle", kwargs={"pk": item.pk}),
    )
    item.refresh_from_db()
    assert item.completed
    assert item.completed_at is not None
    assert item.completed_by == user


@pytest.mark.django_db
def test_checklist_toggle_unchecks(auth_client, project_with_items, user):
    item = ChecklistItem.objects.create(
        project=project_with_items, text="Done", order=0,
        completed=True, completed_by=user,
    )
    auth_client.post(
        reverse("projects:checklist_toggle", kwargs={"pk": item.pk}),
    )
    item.refresh_from_db()
    assert not item.completed
    assert item.completed_at is None
    assert item.completed_by is None


@pytest.mark.django_db
def test_checklist_delete(auth_client, project_with_items):
    item = ChecklistItem.objects.create(
        project=project_with_items, text="Gone soon", order=0,
    )
    response = auth_client.post(
        reverse("projects:checklist_delete", kwargs={"pk": item.pk}),
    )
    assert response.status_code == 200
    assert not ChecklistItem.objects.filter(pk=item.pk).exists()


# ---- Prompt-to-mark-complete tests --------------------------------------

@pytest.mark.django_db
def test_toggle_last_item_triggers_complete_prompt(auth_client, project_with_items):
    item1 = ChecklistItem.objects.create(
        project=project_with_items, text="A", order=0,
    )
    ChecklistItem.objects.create(
        project=project_with_items, text="B", order=1, completed=True,
    )
    # Toggling item1 (the last incomplete one) should surface the prompt.
    response = auth_client.post(
        reverse("projects:checklist_toggle", kwargs={"pk": item1.pk}),
    )
    content = response.content.decode()
    assert "All checklist items complete" in content
    assert "Mark this project as Completed" in content


@pytest.mark.django_db
def test_toggle_non_last_item_does_not_trigger_prompt(auth_client, project_with_items):
    """If other items remain incomplete after a toggle, no prompt."""
    item1 = ChecklistItem.objects.create(
        project=project_with_items, text="A", order=0,
    )
    ChecklistItem.objects.create(
        project=project_with_items, text="B", order=1,
    )
    response = auth_client.post(
        reverse("projects:checklist_toggle", kwargs={"pk": item1.pk}),
    )
    content = response.content.decode()
    assert "All checklist items complete" not in content


@pytest.mark.django_db
def test_no_prompt_when_already_completed_project(auth_client, project_with_items):
    project_with_items.status = ProjectStatus.COMPLETED
    project_with_items.save()
    item = ChecklistItem.objects.create(
        project=project_with_items, text="A", order=0,
    )
    response = auth_client.post(
        reverse("projects:checklist_toggle", kwargs={"pk": item.pk}),
    )
    content = response.content.decode()
    # Even though all items are now complete, the project is ALREADY
    # completed so no prompt should appear.
    assert "Mark this project as Completed" not in content


@pytest.mark.django_db
def test_mark_project_complete_endpoint(auth_client, project_with_items):
    response = auth_client.post(
        reverse("projects:checklist_mark_project_complete",
                kwargs={"pk": project_with_items.pk}),
    )
    assert response.status_code == 200
    project_with_items.refresh_from_db()
    assert project_with_items.status == ProjectStatus.COMPLETED
    assert project_with_items.actual_completion_date is not None


@pytest.mark.django_db
def test_checklist_section_renders_on_project_detail(auth_client, project_with_items):
    ChecklistItem.objects.create(
        project=project_with_items, text="Visible item", order=0,
    )
    response = auth_client.get(
        reverse("projects:detail", kwargs={"pk": project_with_items.pk}),
    )
    content = response.content.decode()
    assert "Checklist" in content
    assert "Visible item" in content


@pytest.mark.django_db
def test_checklist_empty_state_renders(auth_client, project_with_items):
    response = auth_client.get(
        reverse("projects:detail", kwargs={"pk": project_with_items.pk}),
    )
    content = response.content.decode()
    assert "No checklist items yet" in content


@pytest.mark.django_db
def test_overdue_item_shows_red_styling(auth_client, project_with_items):
    yesterday = dt.date.today() - dt.timedelta(days=1)
    ChecklistItem.objects.create(
        project=project_with_items, text="Late", due_date=yesterday, order=0,
    )
    response = auth_client.get(
        reverse("projects:detail", kwargs={"pk": project_with_items.pk}),
    )
    content = response.content.decode()
    assert "text-red-700" in content
