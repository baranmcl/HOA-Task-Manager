import datetime as dt

from django.conf import settings
from django.db import models


class ProjectStatus(models.TextChoices):
    NOT_STARTED = "not_started", "Not started"
    IN_PROGRESS = "in_progress", "In progress"
    DELAYED = "delayed", "Delayed"
    COMPLETED = "completed", "Completed"


class ProjectPriority(models.TextChoices):
    HIGH = "high", "High"
    MEDIUM = "medium", "Medium"
    LOW = "low", "Low"


class RecurrenceRule(models.TextChoices):
    WEEKLY = "weekly", "Weekly"
    MONTHLY = "monthly", "Monthly"
    QUARTERLY = "quarterly", "Quarterly"
    SEMIANNUAL = "semiannual", "Semi-annual"
    ANNUAL = "annual", "Annual"


class InstanceManager(models.Manager):
    """Excludes recurring templates."""

    def get_queryset(self):
        return super().get_queryset().filter(is_recurring_template=False)


class TemplateManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_recurring_template=True)


class Project(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        "projects.ProjectCategory",
        on_delete=models.PROTECT,
        related_name="projects",
    )
    status = models.CharField(
        max_length=16,
        choices=ProjectStatus.choices,
        default=ProjectStatus.NOT_STARTED,
    )
    delay_reason = models.TextField(blank=True)
    priority = models.CharField(
        max_length=8,
        choices=ProjectPriority.choices,
        default=ProjectPriority.MEDIUM,
    )
    projected_completion_date = models.DateField(null=True, blank=True)
    actual_completion_date = models.DateField(null=True, blank=True)
    budget_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    actual_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    vendor_name = models.CharField(max_length=200, blank=True)
    vendor_bid_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    tags = models.ManyToManyField("projects.Tag", related_name="projects", blank=True)

    is_recurring_template = models.BooleanField(default=False)
    recurrence_rule = models.CharField(
        max_length=16,
        choices=RecurrenceRule.choices,
        blank=True,
        default="",
    )
    next_due_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    parent_template = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="template_instances",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    objects = models.Manager()
    instances = InstanceManager()
    templates = TemplateManager()

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["status", "projected_completion_date"]),
            models.Index(fields=["is_recurring_template", "is_active"]),
            models.Index(fields=["category"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).only("status").first()
            old_status = old.status if old else None
        else:
            old_status = None

        if self.status == ProjectStatus.COMPLETED and self.actual_completion_date is None:
            self.actual_completion_date = dt.date.today()
        elif self.status != ProjectStatus.COMPLETED and old_status == ProjectStatus.COMPLETED:
            self.actual_completion_date = None

        super().save(*args, **kwargs)

    @property
    def is_overdue(self) -> bool:
        if self.status == ProjectStatus.COMPLETED:
            return False
        if self.projected_completion_date is None:
            return False
        return self.projected_completion_date < dt.date.today()
