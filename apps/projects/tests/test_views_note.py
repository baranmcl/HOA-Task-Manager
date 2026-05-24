import pytest
from django.urls import reverse

from apps.projects.models import UpdateNote
from apps.roster.models import RosterPerson


@pytest.mark.django_db
def test_add_note(auth_client, project):
    response = auth_client.post(
        reverse("projects:note_add", args=[project.pk]),
        {"body": "Met with vendor."},
    )
    assert response.status_code == 200
    assert UpdateNote.objects.filter(project=project, body="Met with vendor.").exists()


@pytest.mark.django_db
def test_add_empty_note_rejected(auth_client, project):
    response = auth_client.post(
        reverse("projects:note_add", args=[project.pk]),
        {"body": "  "},
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_note_card_renders_linked_roster_name_on_detail_page(auth_client, project, user):
    """When the note's author has a linked RosterPerson, the detail page must
    render that person's name in the note card — not the user's email.
    """
    person = RosterPerson.objects.create(name="Casey Carter")
    user.profile.roster_person = person
    user.profile.save()
    UpdateNote.objects.create(project=project, body="Hello", author=user)

    response = auth_client.get(reverse("projects:detail", args=[project.pk]))
    content = response.content.decode()
    assert "Casey Carter" in content


@pytest.mark.django_db
def test_note_edit_returns_form_with_prefilled_body(auth_client, project, user):
    note = UpdateNote.objects.create(project=project, body="Original body", author=user)
    response = auth_client.get(reverse("projects:note_edit", args=[note.pk]))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Original body" in content
    assert 'name="body"' in content


@pytest.mark.django_db
def test_note_show_returns_read_only_card(auth_client, project, user):
    note = UpdateNote.objects.create(project=project, body="Read me", author=user)
    response = auth_client.get(reverse("projects:note_show", args=[note.pk]))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Read me" in content
    assert "<textarea" not in content


@pytest.mark.django_db
def test_note_save_updates_body_and_keeps_author(auth_client, project, user):
    note = UpdateNote.objects.create(project=project, body="Old body", author=user)
    response = auth_client.post(
        reverse("projects:note_save", args=[note.pk]),
        {"body": "New body"},
    )
    assert response.status_code == 200
    note.refresh_from_db()
    assert note.body == "New body"
    assert note.author == user


@pytest.mark.django_db
def test_note_save_with_empty_body_returns_400(auth_client, project, user):
    note = UpdateNote.objects.create(project=project, body="Keep me", author=user)
    response = auth_client.post(
        reverse("projects:note_save", args=[note.pk]),
        {"body": "   "},
    )
    assert response.status_code == 400
    note.refresh_from_db()
    assert note.body == "Keep me"


@pytest.mark.django_db
def test_note_edit_requires_login(client, project, user):
    note = UpdateNote.objects.create(project=project, body="x", author=user)
    response = client.get(reverse("projects:note_edit", args=[note.pk]))
    assert response.status_code == 302


@pytest.mark.django_db
def test_note_save_requires_login(client, project, user):
    note = UpdateNote.objects.create(project=project, body="x", author=user)
    response = client.post(
        reverse("projects:note_save", args=[note.pk]),
        {"body": "new"},
    )
    assert response.status_code == 302
