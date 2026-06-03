"""Tests for the invite-by-email flow.

The invite view creates a user with set_unusable_password(), then emails
them a link to /reset/<uidb64>/<token>/ — same URL the password reset
flow uses. This test file covers both the invite-send side and the
"can the new user activate their account via the link" side.
"""
import re

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse

from apps.roster.models import RosterPerson


@pytest.fixture
def staff_user(db):
    User = get_user_model()
    return User.objects.create_user(
        username="admin@example.com", email="admin@example.com",
        password="Sufficiently-Long-Pw-1", is_staff=True,
    )


@pytest.fixture
def regular_user(db):
    User = get_user_model()
    return User.objects.create_user(
        username="user@example.com", email="user@example.com",
        password="Sufficiently-Long-Pw-1", is_staff=False,
    )


@pytest.fixture
def staff_client(client, staff_user):
    client.force_login(staff_user)
    return client


@pytest.fixture
def regular_client(client, regular_user):
    client.force_login(regular_user)
    return client


@pytest.mark.django_db
def test_invite_anonymous_user_redirected_to_login(client):
    response = client.get(reverse("accounts:invite_user"))
    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


@pytest.mark.django_db
def test_invite_non_staff_user_forbidden(regular_client):
    response = regular_client.get(reverse("accounts:invite_user"))
    # user_passes_test redirects to login when the predicate fails.
    assert response.status_code == 302


@pytest.mark.django_db
def test_invite_form_renders_for_staff(staff_client):
    response = staff_client.get(reverse("accounts:invite_user"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Invite a user" in content
    assert 'name="email"' in content


@pytest.mark.django_db
def test_invite_creates_user_with_unusable_password(staff_client):
    response = staff_client.post(reverse("accounts:invite_user"), {
        "email": "newbie@example.com",
        "first_name": "New",
        "last_name": "Bie",
    })
    assert response.status_code == 302
    User = get_user_model()
    user = User.objects.get(email="newbie@example.com")
    assert user.username == "newbie@example.com"
    assert user.first_name == "New"
    assert user.last_name == "Bie"
    assert user.is_active is True
    assert user.is_staff is False
    assert not user.has_usable_password()


@pytest.mark.django_db
def test_invite_sends_email_with_activation_url(staff_client):
    staff_client.post(reverse("accounts:invite_user"), {
        "email": "newbie@example.com",
    })
    assert len(mail.outbox) == 1
    sent = mail.outbox[0]
    assert sent.to == ["newbie@example.com"]
    assert "invited" in sent.subject.lower()
    # The body should contain a fully-qualified /reset/<uidb64>/<token>/ URL.
    matches = re.findall(
        r"https?://[^\s]+/accounts/reset/[\w\-]+/[\w\-]+/",
        sent.body,
    )
    assert len(matches) >= 1, f"No activation URL found in body:\n{sent.body}"


@pytest.mark.django_db
def test_invite_links_roster_person_when_provided(staff_client):
    person = RosterPerson.objects.create(name="Newbie")
    staff_client.post(reverse("accounts:invite_user"), {
        "email": "newbie@example.com",
        "roster_person": str(person.pk),
    })
    User = get_user_model()
    user = User.objects.get(email="newbie@example.com")
    assert user.profile.roster_person_id == person.pk


@pytest.mark.django_db
def test_invite_rejects_duplicate_email(staff_client, regular_user):
    """Don't accidentally re-invite an existing user."""
    response = staff_client.post(reverse("accounts:invite_user"), {
        "email": regular_user.email,
    })
    assert response.status_code == 200  # form re-renders with error
    assert "already exists" in response.content.decode()
    # No new user was created.
    User = get_user_model()
    assert User.objects.filter(email=regular_user.email).count() == 1
    assert mail.outbox == []


@pytest.mark.django_db
def test_invite_email_normalized_to_lowercase(staff_client):
    staff_client.post(reverse("accounts:invite_user"), {
        "email": "MixedCase@Example.COM",
    })
    User = get_user_model()
    assert User.objects.filter(email="mixedcase@example.com").exists()


@pytest.mark.django_db
def test_invite_full_activation_flow(staff_client):
    """End-to-end: invite → click link → set password → log in.

    Uses a separate Client() for the invitee (not the staff_client) so
    the activation page renders the unauthenticated layout — in
    production the invitee's browser has no session, and base.html
    only emits the form (via {% block unauth_content %}) when the
    user is anonymous.
    """
    from django.test import Client

    # 1. Staff invites.
    staff_client.post(reverse("accounts:invite_user"), {
        "email": "newbie@example.com",
        "first_name": "New",
    })
    activation_url = re.search(
        r"(/accounts/reset/[\w\-]+/[\w\-]+/)",
        mail.outbox[0].body,
    ).group(1)

    # 2. Invitee (fresh anonymous client) opens the link — form renders.
    invitee_client = Client()
    response = invitee_client.get(activation_url)
    assert response.status_code == 200
    assert "Set your password" in response.content.decode()

    # 3. Invitee submits a password to the same URL.
    response = invitee_client.post(activation_url, {
        "new_password1": "MyChosen-Password-9",
        "new_password2": "MyChosen-Password-9",
    })
    assert response.status_code == 302

    # 4. Invitee can now sign in with the password they chose.
    User = get_user_model()
    invitee = User.objects.get(email="newbie@example.com")
    assert invitee.has_usable_password()
    assert invitee.check_password("MyChosen-Password-9")


@pytest.mark.django_db
def test_sidebar_invite_link_shown_to_staff(staff_client):
    response = staff_client.get(reverse("home"))
    content = response.content.decode()
    assert "Invite user" in content
    assert reverse("accounts:invite_user") in content


@pytest.mark.django_db
def test_sidebar_invite_link_hidden_from_non_staff(regular_client):
    response = regular_client.get(reverse("home"))
    content = response.content.decode()
    assert "Invite user" not in content
