import datetime as dt
import logging

from django.core.management import call_command

from .models import GenerationLog
from .signals import set_actor

logger = logging.getLogger(__name__)


class ActorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            set_actor(request.user)
        else:
            set_actor(None)
        return self.get_response(request)


class RecurringGenerationMiddleware:
    """Runs the recurring-instance generator once per day, lazily.

    PythonAnywhere's free tier has no scheduled tasks, so the generator is
    triggered by the first web request of each day instead of a cron. The
    generator (Task 17) is idempotent and catches up missed cycles, so an
    irregular trigger is fine.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self._maybe_generate()
        return self.get_response(request)

    @staticmethod
    def _maybe_generate():
        today = dt.date.today()
        _, created = GenerationLog.objects.get_or_create(run_date=today)
        if not created:
            return
        # Generated instances must not be attributed to whoever happened to
        # make the first request of the day — run with no signal actor.
        set_actor(None)
        try:
            call_command("generate_recurring_instances")
        except Exception:  # noqa: BLE001 - never let generation break a request
            logger.exception("Recurring instance generation failed")
