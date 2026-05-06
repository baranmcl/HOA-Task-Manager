from django.db import models


class ActiveRosterManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(archived=False)


class RosterPerson(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    role_title = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    active = ActiveRosterManager()

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["archived", "name"]),
        ]

    def __str__(self):
        return self.name
