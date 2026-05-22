from django.conf import settings
from django.db import models


class Attachment(models.Model):
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="attachments",
    )
    file_key = models.CharField(max_length=400)
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size_bytes = models.PositiveBigIntegerField()
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+",
    )

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.original_filename

    @property
    def human_size(self) -> str:
        size = float(self.size_bytes)
        for unit in ["B", "KB", "MB", "GB"]:
            if round(size, 1) < 1000 or unit == "GB":
                if unit == "B":
                    return f"{int(size)} B"
                return f"{size:.1f} {unit}"
            size /= 1000
        return f"{size:.1f} GB"  # pragma: no cover - loop always returns

    @classmethod
    def total_bytes_for_project(cls, project) -> int:
        return cls.objects.filter(project=project).aggregate(
            total=models.Sum("size_bytes")
        )["total"] or 0
