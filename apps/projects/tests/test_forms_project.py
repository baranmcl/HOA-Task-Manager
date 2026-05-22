import pytest

from apps.projects.forms import ProjectForm
from apps.projects.models import ProjectStatus


@pytest.mark.django_db
def test_form_valid_minimal(category):
    form = ProjectForm(data={
        "title": "Test", "category": category.pk,
        "status": ProjectStatus.NOT_STARTED, "priority": "medium",
        "description": "", "tags_text": "",
    })
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_form_delayed_requires_reason(category):
    form = ProjectForm(data={
        "title": "Test", "category": category.pk,
        "status": ProjectStatus.DELAYED, "priority": "medium",
        "description": "", "tags_text": "",
        "delay_reason": "",
    })
    assert not form.is_valid()
    assert "delay_reason" in form.errors


@pytest.mark.django_db
def test_form_creates_tags_from_input(category, user):
    form = ProjectForm(data={
        "title": "Test", "category": category.pk,
        "status": ProjectStatus.NOT_STARTED, "priority": "medium",
        "description": "", "tags_text": "concrete, sprinklers",
    })
    assert form.is_valid(), form.errors
    project = form.save(commit=False)
    project.created_by = user
    project.save()
    form.save_m2m_with_tags(project)
    tag_names = sorted(project.tags.values_list("name", flat=True))
    assert tag_names == ["concrete", "sprinklers"]
