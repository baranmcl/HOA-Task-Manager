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


class RosterGroup(models.Model):
    """A named collection of RosterPeople — typically a committee like
    "Finance Committee" or "Architecture Committee".

    Groups are a *shortcut* for adding multiple people to a project's RACI
    in one click. The relationship is expanded at add-time: when a group
    is used to populate RACI assignments, each member becomes a separate
    RACIAssignment row at that moment. Changing the group's membership
    later does NOT retroactively update existing project assignments —
    this is intentional (predictable audit trail, no spooky retroactive
    changes when a board member leaves a committee mid-project).

    The source_group FK on RACIAssignment records which group an
    assignment came from, so the UI can show "via Finance Committee" as
    an audit annotation. That FK is nullable (SET_NULL on group delete)
    because the assignment itself outlives the group reference — the
    person is still Responsible on the project even if the committee
    disbands.
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def member_count(self):
        return self.memberships.count()

    def active_members(self):
        """RosterPeople in this group who aren't archived."""
        return RosterPerson.objects.filter(
            group_memberships__group=self, archived=False,
        ).order_by("name")


class GroupMembership(models.Model):
    """Join table between RosterGroup and RosterPerson."""
    group = models.ForeignKey(
        RosterGroup, on_delete=models.CASCADE, related_name="memberships",
    )
    person = models.ForeignKey(
        RosterPerson, on_delete=models.CASCADE, related_name="group_memberships",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["group", "person"],
                name="group_membership_unique_group_person",
            ),
        ]
        ordering = ["person__name"]

    def __str__(self):
        return f"{self.person.name} in {self.group.name}"
