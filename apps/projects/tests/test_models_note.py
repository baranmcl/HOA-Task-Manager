import pytest

from apps.projects.models import UpdateNote


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
