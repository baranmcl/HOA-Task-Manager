from django.conf import settings
from django.db import models


class ChecklistItem(models.Model):
    """A single step in a project's checklist.

    Sits alongside Notes and Attachments on the project detail page —
    lightweight, ordered, optionally-due-dated tasks the project owner
    works through. Items don't have their own RACI; the project's
    overall Responsible person manages them.

    When the last item in a project's checklist is completed, the UI
    prompts the user with "All items complete. Mark project as
    Completed?" — the user decides. The model doesn't auto-flip the
    parent project's status.
    """
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE,
        related_name="checklist_items",
    )
    text = models.CharField(max_length=200)
    due_date = models.DateField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)

    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "created_at"]
        indexes = [
            models.Index(fields=["project", "order"]),
            models.Index(fields=["completed", "due_date"]),
        ]

    def __str__(self):
        check = "[x]" if self.completed else "[ ]"
        return f"{check} {self.text}"

    @property
    def is_overdue(self) -> bool:
        if self.completed or self.due_date is None:
            return False
        import datetime as dt
        return self.due_date < dt.date.today()
