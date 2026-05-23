from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    timezone = models.CharField(max_length=64, default="America/New_York")
    roster_person = models.OneToOneField(
        "roster.RosterPerson",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="profile",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile<{self.user.username}>"

    @property
    def display_name(self) -> str:
        """Human-friendly name for activity feeds and audit trails.

        Prefers the linked RosterPerson's name; falls back to the user's
        email and then their username if neither is set.
        """
        if self.roster_person_id:
            return self.roster_person.name
        return self.user.email or self.user.username


class BackupLog(models.Model):
    """One row per day the database backup ran (or attempted to run).

    The unique `run_date` makes the 'first request wins' race in
    BackupMiddleware safe — a second concurrent request raises IntegrityError
    on insert and is treated as a no-op. The remaining fields are
    observability: when did it start/finish, how big was the uploaded file,
    what's its R2 key, and was there an error.
    """

    run_date = models.DateField(unique=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    bytes_uploaded = models.PositiveIntegerField(null=True, blank=True)
    object_key = models.CharField(max_length=200, blank=True)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ["-run_date"]

    def __str__(self):
        status = "ok" if not self.error else "error"
        return f"Backup {self.run_date} ({status})"
