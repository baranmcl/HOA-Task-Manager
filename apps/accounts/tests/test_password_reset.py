"""Tests for the password reset flow (Django built-in views, wired up
with custom templates).
"""
import re

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


@pytest.fixture
def user(db):
    User = get_user_model()
    return User.objects.create_user(
        username="alice@example.com",
        email="alice@example.com",
        password="OldPassword123",
    )


@pytest.mark.django_db
def test_password_reset_form_renders(client):
    response = client.get(reverse("accounts:password_reset"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Reset your password" in content
    assert 'name="email"' in content


@pytest.mark.django_db
def test_password_reset_post_known_email_sends_mail(client, user):
    response = client.post(
        reverse("accounts:password_reset"),
        {"email": user.email},
    )
    assert response.status_code == 302
    assert response.url == reverse("accounts:password_reset_done")
    assert len(mail.outbox) == 1
    sent = mail.outbox[0]
    assert sent.to == [user.email]
    assert "/reset/" in sent.body
    # Subject should be our custom one, not Django's default.
    assert "Reset your HOA Task Manager password" in sent.subject


@pytest.mark.django_db
def test_password_reset_post_unknown_email_redirects_no_mail(client):
    """Django deliberately shows the success page even for unknown
    emails to avoid leaking which addresses are registered."""
    response = client.post(
        reverse("accounts:password_reset"),
        {"email": "ghost@example.com"},
    )
    assert response.status_code == 302
    assert response.url == reverse("accounts:password_reset_done")
    assert mail.outbox == []


@pytest.mark.django_db
def test_password_reset_done_renders(client):
    response = client.get(reverse("accounts:password_reset_done"))
    assert response.status_code == 200
    assert "Check your email" in response.content.decode()


@pytest.mark.django_db
def test_password_reset_confirm_with_valid_token_lets_user_set_password(client, user):
    """End-to-end: token → set new password → can log in with new password."""
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    # Django's PasswordResetConfirmView redirects the initial GET to
    # /reset/<uidb64>/set-password/ after stashing the token in the session.
    response = client.get(
        reverse("accounts:password_reset_confirm",
                kwargs={"uidb64": uidb64, "token": token}),
        follow=True,
    )
    assert response.status_code == 200
    # The follow lands on the set-password form.
    final_url = response.redirect_chain[-1][0]
    assert "set-password" in final_url

    # Now POST a new password to that URL.
    response = client.post(final_url, {
        "new_password1": "BrandNewSecret-999",
        "new_password2": "BrandNewSecret-999",
    })
    assert response.status_code == 302
    assert response.url == reverse("accounts:password_reset_complete")

    # Old password no longer works; new one does.
    user.refresh_from_db()
    assert not user.check_password("OldPassword123")
    assert user.check_password("BrandNewSecret-999")


@pytest.mark.django_db
def test_password_reset_confirm_with_bad_token_shows_invalid_link(client, user):
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    response = client.get(
        reverse("accounts:password_reset_confirm",
                kwargs={"uidb64": uidb64, "token": "invalid-token-here"}),
        follow=True,
    )
    assert response.status_code == 200
    assert "Link expired or invalid" in response.content.decode()


@pytest.mark.django_db
def test_login_page_links_to_password_reset(client):
    response = client.get(reverse("accounts:login"))
    assert response.status_code == 200
    content = response.content.decode()
    assert reverse("accounts:password_reset") in content
    assert "Forgot password?" in content


@pytest.mark.django_db
def test_reset_email_contains_clickable_url(client, user):
    client.post(reverse("accounts:password_reset"), {"email": user.email})
    body = mail.outbox[0].body
    # Should contain a URL of the form .../reset/<uidb64>/<token>/
    matches = re.findall(r"https?://[^\s]+/reset/[\w\-]+/[\w\-]+/", body)
    assert len(matches) >= 1, f"No reset URL found in email body:\n{body}"


@pytest.mark.django_db
def test_password_reset_complete_renders(client):
    response = client.get(reverse("accounts:password_reset_complete"))
    assert response.status_code == 200
    assert "all set" in response.content.decode().lower()
