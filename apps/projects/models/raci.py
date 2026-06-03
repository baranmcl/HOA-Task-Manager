from django.db import models


class RACIRole(models.TextChoices):
    RESPONSIBLE = "responsible", "Responsible"
    ACCOUNTABLE = "accountable", "Accountable"
    CONSULTED = "consulted", "Consulted"
    INFORMED = "informed", "Informed"


class RACIAssignment(models.Model):
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="raci_assignments",
    )
    person = models.ForeignKey(
        "roster.RosterPerson", on_delete=models.PROTECT, related_name="raci_assignments",
    )
    role = models.CharField(max_length=16, choices=RACIRole.choices)
    # If this assignment was created via group-expansion (e.g., adding
    # "Finance Committee" with role=Consulted), record which group. Pure
    # audit annotation — the assignment outlives the group reference, so
    # SET_NULL keeps the row when a group is deleted. Nullable for the
    # common case of individually-added assignments.
    source_group = models.ForeignKey(
        "roster.RosterGroup",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="raci_assignments_via_group",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["project", "person", "role"],
                name="raci_unique_project_person_role",
            )
        ]
        ordering = ["role", "person__name"]

    def __str__(self):
        return f"{self.person.name} — {self.get_role_display()} on {self.project.title}"
