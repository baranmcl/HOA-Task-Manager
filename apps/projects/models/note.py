from django.conf import settings
from django.db import models

from ..markdown_utils import render_note


class UpdateNote(models.Model):
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="notes",
    )
    body = models.TextField()
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_pinned = models.BooleanField(default=False)

    class Meta:
        ordering = ["-is_pinned", "-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["project"],
                condition=models.Q(is_pinned=True),
                name="unique_pinned_note_per_project",
            ),
        ]

    def __str__(self):
        return f"Note on {self.project.title} at {self.created_at:%Y-%m-%d %H:%M}"

    @property
    def rendered_html(self) -> str:
        return render_note(self.body)

    @property
    def is_edited(self) -> bool:
        """True when the note has been edited at least ~1 second after creation.

        Both `created_at` (auto_now_add) and `updated_at` (auto_now) are set
        on insert, but at slightly different moments — they may differ by a
        few microseconds. The 1-second tolerance ignores that initial gap.
        """
        if self.updated_at is None or self.created_at is None:
            return False
        return (self.updated_at - self.created_at).total_seconds() > 1
