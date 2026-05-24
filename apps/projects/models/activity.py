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

    @staticmethod
    def _format_value(value: dict | None) -> str:
        """Render one JSON dict from before_value / after_value as a human string.

        Signal writers store shape-specific dicts:
        - status changes: {"status": "in_progress"}
        - project creation: {"title": "Sprinkler upgrade"}
        - RACI add/remove: {"person": "Mike", "role": "responsible"}
        - board approvals: {"vote_date": "...", "summary": "..."}
        - attachment add/remove: {"filename": "quote.pdf"}

        For unknown shapes, falls back to "key: value, key: value" so we
        never crash on a verb we haven't taught this method about.
        """
        if not value:
            return ""
        # Import here to avoid any chance of a circular import at module load —
        # models/__init__.py imports activity before project/raci.
        from .project import ProjectStatus
        from .raci import RACIRole

        if "status" in value:
            return dict(ProjectStatus.choices).get(value["status"], value["status"])
        if "title" in value and len(value) == 1:
            return value["title"]
        if "person" in value and "role" in value:
            role_label = dict(RACIRole.choices).get(value["role"], value["role"])
            return f"{value['person']} ({role_label})"
        if "filename" in value and len(value) == 1:
            return value["filename"]
        if "vote_date" in value:
            date_str = value["vote_date"]
            summary = value.get("summary") or ""
            return f"vote {date_str}: {summary}" if summary else f"vote {date_str}"
        return ", ".join(f"{k}: {v}" for k, v in value.items())

    @property
    def value_change(self) -> str:
        """Human-readable summary of before → after for templates."""
        before = self._format_value(self.before_value)
        after = self._format_value(self.after_value)
        if before and after:
            return f"{before} → {after}"
        return after or before
