"""Per-request timezone activation.

Django stores datetimes in UTC (USE_TZ=True) but renders templates in the
"current" timezone, set per-request via django.utils.timezone.activate(). This
middleware reads the authenticated user's preferred timezone from their
UserProfile and activates it for the rest of the request, so the {{ ... }}
date filter and {% localtime %} tag automatically convert UTC datetimes to
the user's local time.
"""
import zoneinfo

from django.utils import timezone


class TimezoneMiddleware:
    """Activate request.user.profile.timezone for each authenticated request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tz_name = self._user_timezone(request)
        if tz_name:
            try:
                timezone.activate(zoneinfo.ZoneInfo(tz_name))
            except zoneinfo.ZoneInfoNotFoundError:
                # Stored value is no longer a valid IANA zone (renamed, typo'd
                # via the admin, etc.) — fall back to project default rather
                # than 500 the request.
                timezone.deactivate()
        else:
            timezone.deactivate()
        return self.get_response(request)

    @staticmethod
    def _user_timezone(request) -> str | None:
        if not request.user.is_authenticated:
            return None
        profile = getattr(request.user, "profile", None)
        if profile is None:
            return None
        return profile.timezone or None
