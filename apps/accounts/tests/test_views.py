import datetime as dt

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import BackupLog


@pytest.fixture
def user(db):
    User = get_user_model()
    return User.objects.create_user(
        username="user@example.com",
        email="user@example.com",
        password="Sufficiently-Long-Pw-1",
    )


@pytest.mark.django_db
def test_login_get_renders(client):
    response = client.get(reverse("accounts:login"))
    assert response.status_code == 200
    assert b"Sign in" in response.content


@pytest.mark.django_db
def test_login_post_redirects_to_home(client, user):
    response = client.post(
        reverse("accounts:login"),
        {"username": "user@example.com", "password": "Sufficiently-Long-Pw-1"},
    )
    assert response.status_code == 302
    assert response.url == "/"


@pytest.mark.django_db
def test_logout_redirects_to_login(client, user):
    client.force_login(user)
    response = client.post(reverse("accounts:logout"))
    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


@pytest.mark.django_db
def test_profile_requires_login(client):
    response = client.get(reverse("accounts:profile"))
    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


@pytest.mark.django_db
def test_profile_get_authenticated(client, user):
    client.force_login(user)
    response = client.get(reverse("accounts:profile"))
    assert response.status_code == 200
    assert b"America/New_York" in response.content


@pytest.mark.django_db
def test_profile_update_timezone(client, user):
    client.force_login(user)
    response = client.post(
        reverse("accounts:profile"),
        {"timezone": "America/Los_Angeles"},
    )
    assert response.status_code == 302
    user.profile.refresh_from_db()
    assert user.profile.timezone == "America/Los_Angeles"


@pytest.mark.django_db
def test_profile_form_saves_roster_person(client):
    from apps.roster.models import RosterPerson
    User = get_user_model()
    user = User.objects.create_user(
        username="frank@example.com",
        email="frank@example.com",
        password="Sufficiently-Long-Pw-1",
    )
    person = RosterPerson.objects.create(name="Frank Fox", role_title="Treasurer")
    client.force_login(user)
    response = client.post(reverse("accounts:profile"), {
        "timezone": "America/New_York",
        "roster_person": person.pk,
    })
    assert response.status_code == 302
    user.profile.refresh_from_db()
    assert user.profile.roster_person == person


@pytest.mark.django_db
def test_profile_page_shows_latest_backup(client):
    # Ensure no backups exist before the test
    BackupLog.objects.all().delete()
    User = get_user_model()
    user = User.objects.create_user(
        username="kim@example.com", email="kim@example.com",
        password="Sufficiently-Long-Pw-1",
    )
    BackupLog.objects.create(
        run_date=dt.date.today(),
        finished_at=timezone.now(),
        bytes_uploaded=12345,
        object_key="db-backups/" + dt.date.today().isoformat() + ".sqlite3",
    )
    client.force_login(user)
    response = client.get(reverse("accounts:profile"))
    content = response.content.decode()
    assert "Last backup" in content
    assert "12345 bytes" in content


@pytest.mark.django_db
def test_profile_page_shows_no_backup_yet_when_none(client, monkeypatch):
    # Stub BackupMiddleware._maybe_backup to prevent it from creating a BackupLog entry
    from apps.accounts import middleware as mw_module
    monkeypatch.setattr(mw_module.BackupMiddleware, "_maybe_backup", lambda self: None)

    User = get_user_model()
    user = User.objects.create_user(
        username="leo@example.com", email="leo@example.com",
        password="Sufficiently-Long-Pw-1",
    )
    client.force_login(user)
    response = client.get(reverse("accounts:profile"))
    content = response.content.decode()
    assert "No backups yet" in content
