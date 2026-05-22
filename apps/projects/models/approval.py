from django.db import models


class BoardApproval(models.Model):
    project = models.OneToOneField(
        "projects.Project", on_delete=models.CASCADE, related_name="board_approval",
    )
    motion_text = models.TextField()
    vote_date = models.DateField()
    votes_for = models.PositiveIntegerField(default=0)
    votes_against = models.PositiveIntegerField(default=0)
    votes_abstain = models.PositiveIntegerField(default=0)
    minutes_reference = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-vote_date"]

    def __str__(self):
        return f"Approval for {self.project.title} on {self.vote_date}"

    @property
    def vote_summary(self) -> str:
        return f"{self.votes_for}-{self.votes_against}-{self.votes_abstain}"
