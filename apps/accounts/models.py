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
