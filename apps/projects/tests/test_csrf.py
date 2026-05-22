import pytest
from django.test import Client
from django.urls import reverse


@pytest.mark.django_db
def test_inline_save_rejects_post_without_csrf_token(user, project):
    """With CSRF enforcement on, an HTMX-style POST with no token is rejected."""
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    response = client.post(
        reverse("projects:inline_priority_save", args=[project.pk]),
        {"priority": "high"},
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_inline_save_accepts_post_with_x_csrftoken_header(user, project):
    """A POST carrying the token in the X-CSRFToken header is accepted —
    this is the mechanism base.html's hx-headers config provides."""
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    # GET any page to obtain the csrftoken cookie
    client.get(reverse("projects:detail", args=[project.pk]))
    token = client.cookies["csrftoken"].value
    response = client.post(
        reverse("projects:inline_priority_save", args=[project.pk]),
        {"priority": "high"},
        HTTP_X_CSRFTOKEN=token,
    )
    assert response.status_code == 200
    project.refresh_from_db()
    assert project.priority == "high"


@pytest.mark.django_db
def test_base_template_emits_htmx_csrf_header_config(auth_client, project):
    """base.html must emit the hx-headers attribute so HTMX sends the token."""
    response = auth_client.get(reverse("projects:detail", args=[project.pk]))
    assert b"hx-headers" in response.content
    assert b"X-CSRFToken" in response.content
