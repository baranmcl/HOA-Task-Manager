import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse


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
