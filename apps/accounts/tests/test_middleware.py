"""Tests for the per-request timezone activation."""
import zoneinfo

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory
from django.utils import timezone

from apps.accounts.middleware import TimezoneMiddleware


def _run_middleware(request):
    """Run TimezoneMiddleware and capture the timezone that's active inside it."""
    captured = {}

    def get_response(req):
        captured["tz_name"] = timezone.get_current_timezone_name()
        return HttpResponse()

    TimezoneMiddleware(get_response)(request)
    return captured["tz_name"]


@pytest.mark.django_db
def test_middleware_activates_user_timezone():
    User = get_user_model()
    user = User.objects.create_user(
        username="alice@example.com", email="alice@example.com",
        password="Sufficiently-Long-Pw-1",
    )
    user.profile.timezone = "America/Chicago"
    user.profile.save()

    request = RequestFactory().get("/")
    request.user = user
    assert _run_middleware(request) == "America/Chicago"


@pytest.mark.django_db
def test_middleware_falls_back_on_invalid_timezone():
    User = get_user_model()
    user = User.objects.create_user(
        username="bob@example.com", email="bob@example.com",
        password="Sufficiently-Long-Pw-1",
    )
    user.profile.timezone = "Not/A_Real_Zone"
    user.profile.save()
    timezone.deactivate()  # ensure we're starting from "default"

    request = RequestFactory().get("/")
    request.user = user
    # Should not raise; falls back to the project's TIME_ZONE (UTC).
    assert _run_middleware(request) == "UTC"


@pytest.mark.django_db
def test_middleware_deactivates_for_anonymous():
    timezone.activate(zoneinfo.ZoneInfo("America/Chicago"))  # contaminate
    request = RequestFactory().get("/")
    request.user = AnonymousUser()
    assert _run_middleware(request) == "UTC"
