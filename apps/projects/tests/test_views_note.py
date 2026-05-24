import datetime as dt

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


@pytest.mark.django_db
def test_note_delete_removes_the_row(auth_client, project, user):
    note = UpdateNote.objects.create(project=project, body="Goodbye", author=user)
    response = auth_client.post(reverse("projects:note_delete", args=[note.pk]))
    assert response.status_code == 200
    assert not UpdateNote.objects.filter(pk=note.pk).exists()


@pytest.mark.django_db
def test_note_delete_returns_rebuilt_notes_list(auth_client, project, user):
    UpdateNote.objects.create(project=project, body="Keep me", author=user)
    note_to_delete = UpdateNote.objects.create(
        project=project, body="Delete me", author=user,
    )
    response = auth_client.post(
        reverse("projects:note_delete", args=[note_to_delete.pk]),
    )
    content = response.content.decode()
    assert "Keep me" in content
    assert "Delete me" not in content


@pytest.mark.django_db
def test_note_delete_requires_login(client, project, user):
    note = UpdateNote.objects.create(project=project, body="x", author=user)
    response = client.post(reverse("projects:note_delete", args=[note.pk]))
    assert response.status_code == 302


@pytest.mark.django_db
def test_note_delete_rejects_get(auth_client, project, user):
    note = UpdateNote.objects.create(project=project, body="x", author=user)
    response = auth_client.get(reverse("projects:note_delete", args=[note.pk]))
    assert response.status_code == 405
    assert UpdateNote.objects.filter(pk=note.pk).exists()


@pytest.mark.django_db
def test_note_pin_pins_an_unpinned_note(auth_client, project, user):
    note = UpdateNote.objects.create(project=project, body="x", author=user)
    response = auth_client.post(reverse("projects:note_pin", args=[note.pk]))
    assert response.status_code == 200
    note.refresh_from_db()
    assert note.is_pinned is True


@pytest.mark.django_db
def test_note_pin_unpins_when_already_pinned(auth_client, project, user):
    note = UpdateNote.objects.create(
        project=project, body="x", author=user, is_pinned=True,
    )
    response = auth_client.post(reverse("projects:note_pin", args=[note.pk]))
    assert response.status_code == 200
    note.refresh_from_db()
    assert note.is_pinned is False


@pytest.mark.django_db
def test_pinning_a_new_note_unpins_the_previous_one(auth_client, project, user):
    """Pinning Note B must atomically unpin Note A. The partial unique
    constraint would otherwise raise IntegrityError."""
    note_a = UpdateNote.objects.create(
        project=project, body="A", author=user, is_pinned=True,
    )
    note_b = UpdateNote.objects.create(project=project, body="B", author=user)

    response = auth_client.post(reverse("projects:note_pin", args=[note_b.pk]))
    assert response.status_code == 200

    note_a.refresh_from_db()
    note_b.refresh_from_db()
    assert note_a.is_pinned is False
    assert note_b.is_pinned is True


@pytest.mark.django_db
def test_note_pin_does_not_bump_updated_at(auth_client, project, user):
    """Pin/unpin is metadata, not content — it should not register as an edit."""
    note = UpdateNote.objects.create(project=project, body="x", author=user)
    original_updated_at = note.updated_at

    auth_client.post(reverse("projects:note_pin", args=[note.pk]))

    note.refresh_from_db()
    assert note.updated_at == original_updated_at


@pytest.mark.django_db
def test_note_pin_requires_login(client, project, user):
    note = UpdateNote.objects.create(project=project, body="x", author=user)
    response = client.post(reverse("projects:note_pin", args=[note.pk]))
    assert response.status_code == 302


@pytest.mark.django_db
def test_note_pin_rejects_get(auth_client, project, user):
    note = UpdateNote.objects.create(project=project, body="x", author=user)
    response = auth_client.get(reverse("projects:note_pin", args=[note.pk]))
    assert response.status_code == 405


@pytest.mark.django_db
def test_edited_indicator_absent_on_fresh_note(auth_client, project, user):
    UpdateNote.objects.create(project=project, body="x", author=user)
    response = auth_client.get(reverse("projects:detail", args=[project.pk]))
    assert "(edited)" not in response.content.decode()


@pytest.mark.django_db
def test_edited_indicator_present_after_edit(auth_client, project, user):
    note = UpdateNote.objects.create(project=project, body="x", author=user)
    # Bump updated_at to 5 seconds after created_at so `is_edited` is True.
    UpdateNote.objects.filter(pk=note.pk).update(
        updated_at=note.created_at + dt.timedelta(seconds=5),
    )
    response = auth_client.get(reverse("projects:detail", args=[project.pk]))
    assert "(edited)" in response.content.decode()
