import pytest

from apps.projects.forms import ProjectForm
from apps.projects.models import ProjectCategory, ProjectStatus
from apps.roster.models import RosterPerson


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


@pytest.mark.django_db
def test_initial_responsible_field_present_on_create():
    form = ProjectForm()
    assert "initial_responsible" in form.fields


@pytest.mark.django_db
def test_initial_responsible_field_absent_on_edit(project):
    form = ProjectForm(instance=project)
    assert "initial_responsible" not in form.fields


@pytest.mark.django_db
def test_initial_responsible_queryset_excludes_archived():
    RosterPerson.objects.create(name="Active Alice")
    RosterPerson.objects.create(name="Archived Andy", archived=True)
    form = ProjectForm()
    names = list(form.fields["initial_responsible"].queryset.values_list("name", flat=True))
    assert "Active Alice" in names
    assert "Archived Andy" not in names


@pytest.mark.django_db
def test_initial_responsible_is_optional():
    """The create form must validate when initial_responsible is left blank."""
    category = ProjectCategory.objects.create(name="Test Cat", display_order=99)
    form = ProjectForm(data={
        "title": "P", "category": category.pk,
        "status": "not_started", "priority": "medium",
        "description": "", "tags_text": "",
    })
    assert form.is_valid(), form.errors
