"""Per-request timezone activation.

Django stores datetimes in UTC (USE_TZ=True) but renders templates in the
"current" timezone, set per-request via django.utils.timezone.activate(). This
middleware reads the authenticated user's preferred timezone from their
UserProfile and activates it for the rest of the request, so the {{ ... }}
date filter and {% localtime %} tag automatically convert UTC datetimes to
the user's local time.
"""
import datetime as dt
import logging
import zoneinfo

from django.core.management import call_command
from django.utils import timezone

from apps.accounts.models import BackupLog

backup_logger = logging.getLogger(__name__)


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


class BackupMiddleware:
    """Runs the database backup once per day, lazily.

    PythonAnywhere's free tier has no scheduled tasks, so the backup is
    triggered by the first web request of each day. The unique constraint
    on BackupLog.run_date makes 'first request wins' race-safe.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self._maybe_backup()
        return self.get_response(request)

    @staticmethod
    def _maybe_backup():
        today = dt.date.today()
        # get_or_create races on the unique run_date — the second caller's
        # IntegrityError surfaces as `created=False` so only one path runs
        # the actual backup.
        _, created = BackupLog.objects.get_or_create(run_date=today)
        if not created:
            return
        try:
            call_command("backup_database")
        except Exception:  # noqa: BLE001 - never let backup break a request
            backup_logger.exception("Database backup failed")
