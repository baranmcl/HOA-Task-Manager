import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.roster.models import RosterPerson


@pytest.fixture
def user(db):
    User = get_user_model()
    return User.objects.create_user(
        username="user@example.com",
        email="user@example.com",
        password="Sufficiently-Long-Pw-1",
    )


@pytest.fixture
def auth_client(client, user):
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_list_requires_login(client):
    response = client.get(reverse("roster:list"))
    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


@pytest.mark.django_db
def test_list_renders_active_only_by_default(auth_client):
    RosterPerson.objects.create(name="Active Alice")
    RosterPerson.objects.create(name="Archived Bob", archived=True)
    response = auth_client.get(reverse("roster:list"))
    assert response.status_code == 200
    assert b"Active Alice" in response.content
    assert b"Archived Bob" not in response.content


@pytest.mark.django_db
def test_list_show_archived(auth_client):
    RosterPerson.objects.create(name="Archived Bob", archived=True)
    response = auth_client.get(reverse("roster:list") + "?show_archived=1")
    assert response.status_code == 200
    assert b"Archived Bob" in response.content


@pytest.mark.django_db
def test_create_person(auth_client):
    response = auth_client.post(reverse("roster:create"), {
        "name": "New Person",
        "email": "new@example.com",
        "phone": "",
        "role_title": "Member",
        "notes": "",
    })
    assert response.status_code == 302
    assert RosterPerson.objects.filter(name="New Person").exists()


@pytest.mark.django_db
def test_detail_renders(auth_client):
    p = RosterPerson.objects.create(name="Detail Person")
    response = auth_client.get(reverse("roster:detail", args=[p.pk]))
    assert response.status_code == 200
    assert b"Detail Person" in response.content


@pytest.mark.django_db
def test_edit_person(auth_client):
    p = RosterPerson.objects.create(name="Old Name")
    response = auth_client.post(reverse("roster:edit", args=[p.pk]), {
        "name": "New Name",
        "email": "",
        "phone": "",
        "role_title": "",
        "notes": "",
    })
    assert response.status_code == 302
    p.refresh_from_db()
    assert p.name == "New Name"


@pytest.mark.django_db
def test_archive_person(auth_client):
    p = RosterPerson.objects.create(name="To Archive")
    response = auth_client.post(reverse("roster:archive", args=[p.pk]))
    assert response.status_code == 302
    p.refresh_from_db()
    assert p.archived is True


@pytest.mark.django_db
def test_unarchive_person(auth_client):
    p = RosterPerson.objects.create(name="To Unarchive", archived=True)
    response = auth_client.post(reverse("roster:unarchive", args=[p.pk]))
    assert response.status_code == 302
    p.refresh_from_db()
    assert p.archived is False
