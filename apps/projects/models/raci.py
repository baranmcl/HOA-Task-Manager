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
