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

    class Meta:
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"Note on {self.project.title} at {self.created_at:%Y-%m-%d %H:%M}"

    @property
    def rendered_html(self) -> str:
        return render_note(self.body)
