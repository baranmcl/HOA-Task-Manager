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
