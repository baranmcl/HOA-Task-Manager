from django.conf import settings
from django.db import models


class ActivityLog(models.Model):
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE,
        null=True, blank=True, related_name="activity_log",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+",
    )
    verb = models.CharField(max_length=120)
    before_value = models.JSONField(null=True, blank=True)
    after_value = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["project", "-created_at"]),
        ]

    def __str__(self):
        target = f" on {self.project.title}" if self.project_id else ""
        return f"{self.actor} {self.verb}{target}"
