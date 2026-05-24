import datetime as dt

import pytest
from django.db import IntegrityError

from apps.projects.models import Project, UpdateNote


@pytest.mark.django_db
def test_create_note(project, user):
    n = UpdateNote.objects.create(project=project, body="Met with vendor.", author=user)
    assert n.body == "Met with vendor."


@pytest.mark.django_db
def test_notes_ordered_newest_first(project, user):
    n1 = UpdateNote.objects.create(project=project, body="First", author=user)
    n2 = UpdateNote.objects.create(project=project, body="Second", author=user)
    notes = list(UpdateNote.objects.filter(project=project))
    assert notes[0].pk == n2.pk
    assert notes[1].pk == n1.pk


@pytest.mark.django_db
def test_rendered_html_property(project, user):
    n = UpdateNote.objects.create(project=project, body="**Bold**", author=user)
    assert "<strong>Bold</strong>" in n.rendered_html


@pytest.mark.django_db
def test_pinned_note_is_unique_per_project(project, user):
    UpdateNote.objects.create(project=project, body="First", author=user, is_pinned=True)
    with pytest.raises(IntegrityError):
        UpdateNote.objects.create(project=project, body="Second", author=user, is_pinned=True)


@pytest.mark.django_db
def test_pinned_notes_on_different_projects_dont_conflict(category, user):
    p1 = Project.objects.create(title="P1", category=category, created_by=user)
    p2 = Project.objects.create(title="P2", category=category, created_by=user)
    UpdateNote.objects.create(project=p1, body="One", author=user, is_pinned=True)
    UpdateNote.objects.create(project=p2, body="Two", author=user, is_pinned=True)
    assert UpdateNote.objects.filter(is_pinned=True).count() == 2


@pytest.mark.django_db
def test_pinned_note_appears_first_in_ordering(project, user):
    older_unpinned = UpdateNote.objects.create(project=project, body="Older", author=user)
    UpdateNote.objects.create(project=project, body="Newer", author=user)
    UpdateNote.objects.filter(pk=older_unpinned.pk).update(is_pinned=True)
    notes = list(UpdateNote.objects.filter(project=project))
    assert notes[0].body == "Older"


@pytest.mark.django_db
def test_is_edited_false_on_fresh_note(project, user):
    note = UpdateNote.objects.create(project=project, body="x", author=user)
    note.refresh_from_db()
    assert note.is_edited is False


@pytest.mark.django_db
def test_is_edited_true_after_save_with_delay(project, user):
    note = UpdateNote.objects.create(project=project, body="x", author=user)
    UpdateNote.objects.filter(pk=note.pk).update(
        updated_at=note.created_at + dt.timedelta(seconds=5),
    )
    note.refresh_from_db()
    assert note.is_edited is True
