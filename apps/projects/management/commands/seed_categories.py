from django.core.management.base import BaseCommand

from apps.projects.models import ProjectCategory

SEED = [
    ("Capital", 1),
    ("Operational", 2),
    ("Recurring", 3),
    ("Security", 4),
    ("Maintenance", 5),
    ("Financial", 6),
    ("Misc", 7),
]


class Command(BaseCommand):
    help = "Seed the fixed ProjectCategory list (idempotent)."

    def handle(self, *args, **options):
        created = 0
        for name, order in SEED:
            _, was_created = ProjectCategory.objects.get_or_create(
                name=name, defaults={"display_order": order}
            )
            if was_created:
                created += 1
        self.stdout.write(self.style.SUCCESS(
            f"Seeded categories: {created} created, {len(SEED) - created} already existed."
        ))
