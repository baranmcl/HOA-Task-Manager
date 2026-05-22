import datetime as dt

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.projects.models import Project, ProjectStatus, RACIAssignment
from apps.projects.recurring import advance, suffix_for


class Command(BaseCommand):
    help = "Generate Project instances from active recurring templates due today or earlier."

    def handle(self, *args, **options):
        today = dt.date.today()
        templates = Project.templates.filter(
            is_active=True,
            next_due_date__lte=today,
        )
        total = 0
        for template in templates:
            total += self._catch_up(template, today)
        self.stdout.write(self.style.SUCCESS(f"Generated {total} instance(s)."))

    @transaction.atomic
    def _catch_up(self, template: Project, today: dt.date) -> int:
        if not template.recurrence_rule or not template.next_due_date:
            return 0
        count = 0
        while template.next_due_date and template.next_due_date <= today:
            self._make_instance(template, template.next_due_date)
            template.next_due_date = advance(template.recurrence_rule, template.next_due_date)
            count += 1
        template.save()
        return count

    def _make_instance(self, template: Project, due: dt.date) -> Project:
        suffix = suffix_for(template.recurrence_rule, due)
        title = f"{template.title} — {suffix}"
        next_due = advance(template.recurrence_rule, due)

        instance = Project.objects.create(
            title=title,
            description=template.description,
            category=template.category,
            status=ProjectStatus.NOT_STARTED,
            priority=template.priority,
            projected_completion_date=next_due,
            is_recurring_template=False,
            is_active=True,
            parent_template=template,
            created_by=template.created_by,
        )
        instance.tags.set(template.tags.all())
        for raci in template.raci_assignments.all():
            RACIAssignment.objects.create(
                project=instance, person=raci.person, role=raci.role,
            )
        return instance
