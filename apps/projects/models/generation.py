from django.db import models


class GenerationLog(models.Model):
    """One row per day the recurring-instance generator ran.

    The app has no scheduler (PythonAnywhere free tier). Generation is
    triggered lazily by web traffic — RecurringGenerationMiddleware runs
    the generator on the first request of each day, recording it here so
    later requests that day skip it. The unique run_date makes the
    'first request wins' race safe.
    """

    run_date = models.DateField(unique=True)
    ran_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-run_date"]

    def __str__(self):
        return f"Recurring generation ran {self.run_date}"
